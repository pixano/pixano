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

import io
from functools import cache
from typing import Any, Iterable

import httpx
from PIL import Image
from pixano_inference_client import EmbeddingRequest, PixanoInferenceError, SyncPixanoInferenceClient
from pydantic import Field

from pixano.inference.media import bytes_to_data_uri

from ..reader import JobReader
from ..writer import JobWriter, check_embedding_space
from .base import Chunk, JobKind, JobParams, Outcome, QuarantinedItem, TransientError


# La table des vues image, et celle des enregistrements. Ce sont les noms canoniques de Pixano.
IMAGE_TABLE = "images"
RECORD_TABLE = "records"

# Les réponses qui disent « reviens plus tard » : délai dépassé, trop de requêtes, service
# indisponible. Le client rejoue déjà seul les 502, 503 et 504 ; ce qui arrive jusqu'ici a
# survécu à ses reprises et relève de la file.
TRANSIENT_STATUSES = frozenset({408, 429, 502, 503, 504})

# Les réponses qui disent « cette requête ne passera jamais », quel que soit son contenu : pas
# de droit, pas de route, pas de modèle. Découper le lot n'y changerait rien.
REQUEST_STATUSES = frozenset({401, 403, 404, 405})

# Côté de l'image témoin : la plus petite que le serveur accepte sans discuter. Elle ne sert
# qu'à savoir si le serveur embarque encore quelque chose, pas à produire un vecteur.
WITNESS_IMAGE_SIDE = 16

# Le statut que le client donne à une erreur quand le serveur n'a rien répondu du tout —
# connexion refusée, délai dépassé. Il l'enveloppe dans une PixanoInferenceError plutôt que de
# laisser passer l'erreur httpx.
NO_RESPONSE = 0


@cache
def witness_image() -> str:
    """Une image générée, en octets, que le serveur doit savoir embarquer.

    Quand un lot entier est refusé image par image, elle départage la panne de l'inférence du lot
    réellement corrompu : le seuil « deux images refusées valent une panne » qu'elle remplace
    faisait dépendre la décision de la taille du lot, et le dernier chunk d'un dataset n'a
    souvent qu'une image.
    """
    image = Image.new("RGB", (WITNESS_IMAGE_SIDE, WITNESS_IMAGE_SIDE), (128, 128, 128))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return bytes_to_data_uri(buffer.getvalue())


class EmbeddingsParams(JobParams):
    """Paramètres du calcul d'embeddings.

    Attributes:
        model: Le nom du modèle tel que l'inference le déclare.
        chunk_size: Enregistrements par chunk. C'est aussi la taille du lot envoyé à
            l'inference : un chunk est un appel. Le défaut de 8 est mesuré, pas supposé —
            voir « Chunk size, measured » dans docs/specs/backend-processing.md. Sur CPU,
            grossir le lot ralentit le job au lieu de l'accélérer, et un petit chunk réduit
            en prime ce qu'une reprise doit refaire. Sur GPU l'arbitrage s'inversera
            probablement : c'est précisément pourquoi ce paramètre existe.
        normalize: Normaliser les vecteurs, pour que la similarité cosinus soit un produit
            scalaire.
        max_retries: Reprises courtes d'un appel en échec passager, faites par le client
            d'inférence avant de rendre la main. Au-delà, le chunk est rendu à la file, qui le
            rejouera plus tard.
        request_timeout_s: Au-delà, l'appel est considéré perdu. Généreux, parce qu'un modèle
            sur CPU met du temps et qu'abandonner trop tôt transformerait de la lenteur en
            échec.
    """

    model: str = Field(default="clip", min_length=1)
    chunk_size: int = Field(default=8, ge=1, le=256)
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

        Le modèle est vérifié ici, avant tout calcul : un job qui ne pourra pas écrire ses
        vecteurs doit échouer à la planification, pas après avoir fait tourner l'inférence sur
        tout le dataset.

        Raises:
            ValueError: Le dataset porte déjà des embeddings d'un autre modèle.
        """
        check_embedding_space(reader.dataset.record_embedding_space(), params.model)
        batch: list[str] = []
        for record_id in reader.ids(RECORD_TABLE):
            batch.append(record_id)
            if len(batch) == params.chunk_size:
                yield Chunk(payload={"record_ids": batch}, task_count=len(batch))
                batch = []
        if batch:
            yield Chunk(payload={"record_ids": batch}, task_count=len(batch))

    def process(self, reader: JobReader, payload: dict[str, Any], params: EmbeddingsParams) -> dict[str, Any]:
        """Embarquer un lot d'images et rendre leurs vecteurs, avec le sort de chaque enregistrement.

        Trois issues par enregistrement. Sans vue image, il est **écarté** : ce n'est pas une
        erreur, c'est un enregistrement auquel ce calcul ne s'applique pas. Avec une image
        introuvable ou que l'inférence refuse, il part en **quarantaine**. Sinon il est
        **produit**.

        Raises:
            TransientError: L'inférence ne répond pas, ou refuse tout le lot sans qu'aucune
                image n'y soit pour rien.
        """
        record_ids: list[str] = payload["record_ids"]
        images = self._images_of(reader, record_ids) if record_ids else {}

        candidates: list[tuple[str, str]] = []
        # Les images envoyées par chemin, pour pouvoir en renvoyer une en octets si le serveur
        # les refuse toutes alors qu'il embarque encore l'image témoin.
        by_path: dict[str, Any] = {}
        quarantined: list[dict[str, Any]] = []
        skipped = 0
        carried = 0
        for record_id in record_ids:
            image = images.get(record_id)
            if image is None:
                skipped += 1
                continue
            resolved = reader.resolve_media(IMAGE_TABLE, image)
            if resolved is None:
                quarantined.append({"item_id": record_id, "reason": "media not found"})
                continue
            candidates.append((record_id, resolved.value))
            carried += int(resolved.carried_bytes)
            if not resolved.carried_bytes:
                by_path[record_id] = image

        client = SyncPixanoInferenceClient(
            self.inference_url, api_key=self.api_key or None, max_retries=params.max_retries
        )
        embedded, refused = self._embed_isolating(client, candidates, params)
        if refused and not embedded:
            # Tout le lot est refusé, image par image. Une inférence en panne refuse tout ; un
            # lot entièrement corrompu aussi. Ce n'est pas la taille du lot qui départage — le
            # dernier chunk d'un dataset n'a souvent qu'une image — mais le serveur lui-même,
            # sur une image qu'on sait bonne.
            self._blame_the_server_or_the_images(client, reader, refused, by_path, params)
        quarantined.extend(
            {"item_id": record_id, "reason": "refused by the inference server", "detail": detail}
            for record_id, detail in refused
        )

        return {
            "record_ids": [record_id for record_id, _ in embedded],
            "vectors": [vector for _, vector in embedded],
            "skipped": skipped,
            "quarantined": quarantined,
            "carried_bytes": carried,
        }

    def outcome(self, result: dict[str, Any], payload: dict[str, Any], task_count: int) -> Outcome:
        """Ce que `process` a constaté pour chaque enregistrement."""
        return Outcome(
            produced=len(result["vectors"]),
            skipped=result["skipped"],
            quarantined=[QuarantinedItem.model_validate(item) for item in result["quarantined"]],
        )

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

    def _blame_the_server_or_the_images(
        self,
        client: SyncPixanoInferenceClient,
        reader: JobReader,
        refused: list[tuple[str, dict[str, Any]]],
        by_path: dict[str, Any],
        params: EmbeddingsParams,
    ) -> None:
        """Décider, sur un lot entièrement refusé, si c'est le serveur ou les images.

        Une image témoin, générée ici, est envoyée en octets : refusée, le serveur ne va pas
        bien et le chunk est rejoué plus tard. Acceptée, les images sont en cause — sauf si
        elles avaient été désignées par chemin : le serveur peut ne pas lire le stockage qu'on
        lui a dit de monter, et refuser alors tout chemin sans qu'aucune image n'y soit pour
        rien. L'une d'elles est donc renvoyée en octets ; si elle passe, c'est le montage, et le
        chunk est rejoué avec la raison, plutôt que trois cents images saines en quarantaine.

        Raises:
            TransientError: Le serveur refuse l'image témoin, ou ne lit pas ses médias par chemin.
        """
        try:
            self._embed(client, [witness_image()], params)
        except (httpx.TransportError, PixanoInferenceError) as error:
            raise TransientError(f"l'inférence refuse même l'image témoin : {error}") from error

        first_by_path = next((record_id for record_id, _ in refused if record_id in by_path), None)
        if first_by_path is None:
            return
        found = reader.dataset.get_view_binary(IMAGE_TABLE, by_path[first_by_path].id)
        if found is None or not found[0]:
            return
        try:
            self._embed(client, [bytes_to_data_uri(found[0])], params)
        except (httpx.TransportError, PixanoInferenceError):
            # Refusée en octets aussi : l'image est bien en cause.
            return
        raise TransientError(
            f"l'inférence refuse les images par chemin mais accepte la même en octets ({first_by_path}) : "
            "elle ne lit pas le stockage des médias — vérifier PIXANO_INFERENCE_MEDIA_ROOT et son montage"
        )

    @staticmethod
    def _images_of(reader: JobReader, record_ids: list[str]) -> dict[str, Any]:
        """La vue image de chaque enregistrement du lot, quand elle existe.

        Un enregistrement peut porter plusieurs vues image — nuScenes en a six, une par
        caméra. Ce type en embarque **une**, la première que LanceDB rend, et n'offre pas encore
        de quoi choisir laquelle : c'est un paramètre `view` à ajouter avec les types de l'étape
        2, quand on saura ce que la pré-annotation attend d'un enregistrement multi-vues.
        """
        rows = reader.dataset.get_data(IMAGE_TABLE, record_ids=list(record_ids)) or []
        by_record: dict[str, Any] = {}
        for row in rows:
            by_record.setdefault(row.record_id, row)
        return by_record

    def _embed_isolating(
        self, client: SyncPixanoInferenceClient, candidates: list[tuple[str, str]], params: EmbeddingsParams
    ) -> tuple[list[tuple[str, list[float]]], list[tuple[str, dict[str, Any]]]]:
        """Embarquer un lot, et s'il est refusé, trouver la ou les images en cause.

        L'inférence répond 500 aussi bien pour une image corrompue que pour un chemin absent, et
        refuse alors le lot entier : son code de retour ne désigne pas le coupable. On coupe le
        lot en deux et on recommence, jusqu'à isoler les images qui échouent seules. Un lot de
        huit avec une image corrompue coûte sept appels au lieu d'un — mais seulement le jour où
        une image est corrompue, et les sept autres sont sauvées.

        Une image n'est accusée que sur une **réponse** du serveur, jamais sur son silence. Une
        panne de connexion au milieu de la recherche rend tout le chunk transitoire : coupée en
        plein job, l'inférence redémarrait, un appel passait, les suivants trouvaient la
        connexion refusée — et sept images saines partaient en quarantaine.

        Returns:
            Les vecteurs obtenus, et les enregistrements refusés avec le détail du refus.

        Raises:
            TransientError: L'inférence ne répond pas ou demande de revenir plus tard.
            PixanoInferenceError: Une erreur qui ne dépend d'aucune image — un modèle inconnu,
                un accès refusé. Elle est fatale au chunk.
        """
        if not candidates:
            return [], []
        try:
            vectors = self._embed(client, [reference for _, reference in candidates], params)
        except httpx.TransportError as error:
            raise TransientError(f"l'inférence ne répond pas : {error}") from error
        except PixanoInferenceError as error:
            if error.status_code == NO_RESPONSE:
                raise TransientError(f"l'inférence ne répond pas : {error}") from error
            if error.status_code in TRANSIENT_STATUSES:
                raise TransientError(f"l'inférence demande de revenir plus tard : {error}") from error
            if error.status_code in REQUEST_STATUSES:
                raise
            if len(candidates) == 1:
                detail = {"status": error.status_code, "code": error.code, "message": str(error.message)[:500]}
                return [], [(candidates[0][0], detail)]
            middle = len(candidates) // 2
            left_ok, left_ko = self._embed_isolating(client, candidates[:middle], params)
            right_ok, right_ko = self._embed_isolating(client, candidates[middle:], params)
            return left_ok + right_ok, left_ko + right_ko
        return [(record_id, vector) for (record_id, _), vector in zip(candidates, vectors, strict=True)], []

    @staticmethod
    def _embed(
        client: SyncPixanoInferenceClient, references: list[str], params: EmbeddingsParams
    ) -> list[list[float]]:
        """Un appel d'embedding.

        L'appel passe par le client officiel plutôt que par une requête HTTP écrite à la main :
        les vecteurs voyagent en tableau numpy encodé, et redeviner cet encodage serait une
        supposition de plus à maintenir. Le client rejoue lui-même les échecs brefs.
        """
        request = EmbeddingRequest(model=params.model, image=references, normalize=params.normalize)
        response = client.embedding(request, timeout=params.request_timeout_s)
        return [list(vector) for vector in response.data.embeddings.to_numpy()]
