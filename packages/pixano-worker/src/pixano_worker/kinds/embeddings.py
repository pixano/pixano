# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Calcul d'embeddings : un vecteur par enregistrement, depuis sa vue image.

Le premier type de job réel. Il sert de référence aux suivants — pré-annotation, suivi vidéo —
parce qu'il exerce tout ce qu'ils exerceront : lire un dataset, désigner des médias sans faire
transiter d'octets quand c'est évitable, appeler l'inférence par lots, distinguer un échec
transitoire d'un échec définitif, et écrire un résultat que rejouer ne duplique pas.
"""

import logging
from typing import Any, Iterable

import httpx
from pixano_inference_client import EmbeddingRequest, PixanoInferenceError, SyncPixanoInferenceClient
from pydantic import Field

from ..reader import JobReader
from ..writer import JobWriter
from .base import Chunk, JobKind, JobParams


logger = logging.getLogger("pixano-worker")

# La table des vues image, et celle des enregistrements. Ce sont les noms canoniques de Pixano.
IMAGE_TABLE = "images"
RECORD_TABLE = "records"


class EmbeddingsParams(JobParams):
    """Paramètres du calcul d'embeddings.

    Attributes:
        model: Le nom du modèle tel que l'inference le déclare.
        chunk_size: Enregistrements par chunk. C'est aussi la taille du lot envoyé à
            l'inference : un chunk est un appel.
        normalize: Normaliser les vecteurs, pour que la similarité cosinus soit un produit
            scalaire.
        max_retries: Nombre de reprises d'un appel transitoire, à l'intérieur du chunk. Le
            moteur ne rejoue que les chunks dont le worker est mort, donc un 503 doit être
            absorbé ici.
        request_timeout_s: Au-delà, l'appel est considéré perdu. Généreux, parce qu'un modèle
            sur CPU met du temps et qu'abandonner trop tôt transformerait de la lenteur en
            échec.
    """

    model: str = Field(default="clip", min_length=1)
    chunk_size: int = Field(default=16, ge=1, le=256)
    normalize: bool = True
    max_retries: int = Field(default=3, ge=0, le=10)
    request_timeout_s: float = Field(default=300.0, gt=0)


class EmbeddingsKind(JobKind[EmbeddingsParams]):
    """Calcule un vecteur par enregistrement et l'écrit dans le dataset."""

    name = "embeddings"
    params_model = EmbeddingsParams
    # Un embedding est bien la sortie d'un modèle.
    source_type = "model"

    def __init__(self, inference_url: str = "", api_key: str = "") -> None:
        """Lier ce type au serveur d'inférence que le worker connaît."""
        self.inference_url = inference_url.rstrip("/")
        self.api_key = api_key

    def plan(self, reader: JobReader, params: EmbeddingsParams) -> Iterable[Chunk]:
        """Découper les enregistrements du dataset en lots.

        Le chunk ne porte que des identifiants. Les images seront lues à l'exécution — y
        mettre les références résolues gonflerait la table des chunks du poids du dataset
        pour les datasets dont les médias sont embarqués.
        """
        batch: list[str] = []
        for record_id in reader.ids(RECORD_TABLE):
            batch.append(record_id)
            if len(batch) == params.chunk_size:
                yield Chunk(payload={"record_ids": batch}, task_count=len(batch))
                batch = []
        if batch:
            yield Chunk(payload={"record_ids": batch}, task_count=len(batch))

    def process(self, reader: JobReader, payload: dict[str, Any], params: EmbeddingsParams) -> dict[str, Any]:
        """Embarquer un lot d'images et rendre leurs vecteurs.

        Les enregistrements sans image exploitable sont écartés du lot plutôt que de faire
        échouer le chunk : une image manquante est un défaut de cet item, pas du traitement.
        """
        record_ids: list[str] = payload["record_ids"]
        images = self._images_of(reader, record_ids) if record_ids else {}

        references: list[str] = []
        embedded_ids: list[str] = []
        carried = 0
        for record_id in record_ids:
            image = images.get(record_id)
            resolved = reader.resolve_media(IMAGE_TABLE, image) if image is not None else None
            if resolved is None:
                logger.debug("enregistrement %s sans image exploitable, écarté", record_id)
                continue
            references.append(resolved.value)
            embedded_ids.append(record_id)
            carried += int(resolved.carried_bytes)

        if not references:
            return {"record_ids": [], "vectors": [], "carried_bytes": 0}

        vectors = self._embed(references, params)
        return {"record_ids": embedded_ids, "vectors": vectors, "carried_bytes": carried}

    def write(
        self, writer: JobWriter, result: dict[str, Any], payload: dict[str, Any], params: EmbeddingsParams
    ) -> None:
        """Écrire un vecteur par enregistrement, en remplaçant le précédent.

        La clé est l'enregistrement : recalculer les embeddings d'un dataset remplace les
        vecteurs au lieu d'en empiler une seconde série.
        """
        vectors = result["vectors"]
        if not vectors:
            return
        writer.write_record_embeddings(record_ids=result["record_ids"], vectors=vectors, model=params.model)

    @staticmethod
    def _images_of(reader: JobReader, record_ids: list[str]) -> dict[str, Any]:
        """La vue image de chaque enregistrement du lot, quand elle existe."""
        rows = reader.dataset.get_data(IMAGE_TABLE, record_ids=list(record_ids)) or []
        by_record: dict[str, Any] = {}
        for row in rows:
            by_record.setdefault(row.record_id, row)
        return by_record

    def _embed(self, references: list[str], params: EmbeddingsParams) -> list[list[float]]:
        """Appeler l'inference, en absorbant les échecs de circonstance.

        Un service saturé ou une route expirée veut dire « reviens plus tard », pas « ce
        travail est impossible ». Rejouer ici évite de rendre le chunk au moteur, ce qui
        coûterait une réclamation complète et finirait par épuiser son compteur de tentatives
        sur un incident passager.

        L'appel passe par le client officiel plutôt que par une requête HTTP écrite à la
        main : les vecteurs voyagent en tableau numpy encodé, et redeviner cet encodage serait
        une supposition de plus à maintenir.

        Raises:
            RuntimeError: L'inference n'a pas répondu après les reprises prévues.
        """
        client = SyncPixanoInferenceClient(self.inference_url, api_key=self.api_key or None)
        request = EmbeddingRequest(model=params.model, image=references, normalize=params.normalize)
        last: Exception | None = None

        for attempt in range(params.max_retries + 1):
            try:
                response = client.embedding(request, timeout=params.request_timeout_s)
                return [list(vector) for vector in response.data.embeddings.to_numpy()]
            except (PixanoInferenceError, httpx.TransportError) as error:
                last = error
                if attempt < params.max_retries:
                    logger.info("appel d'embedding rejoué (%s), tentative %d", error, attempt + 2)

        raise RuntimeError(f"l'inference n'a pas répondu après {params.max_retries + 1} tentatives : {last}")
