# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Ce qu'on donne à l'inference pour désigner un média.

Le plan veut que les médias ne transitent jamais par Pixano : sur un dataset de plusieurs
téraoctets, envoyer les octets sature le réseau là où un chemin suffit. Mais un dataset
importé en mode `embed` porte ses images **dans** LanceDB, et il n'existe alors aucun chemin
à donner — c'est le cas des datasets en place aujourd'hui, et le calcul d'embeddings existant
fonctionne précisément parce qu'il envoie les octets.

Ce module applique donc une **préférence, pas une interdiction** : le chemin quand il existe,
les octets quand c'est la seule route. Et il dit lequel des deux il a choisi, pour que le coût
soit mesurable et visible dans les logs au lieu d'être découvert sur un gros dataset.
"""

import logging
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Protocol

from pixano.inference.media import bytes_to_data_uri


logger = logging.getLogger("pixano-worker")

# Ce que l'inference sait aller chercher elle-même. Les autres schémas n'ont pas de sens pour
# elle : un chemin local ne vaut que s'il est sous une racine qu'elle a déclarée.
REMOTE_SCHEMES = ("http://", "https://", "s3://")


class MediaSource(Protocol):
    """Le peu qu'il faut d'un dataset pour aller chercher un média embarqué."""

    def get_view_binary(self, table_name: str, row_id: str) -> tuple[bytes, str] | None:
        """Les octets d'une vue, et leur type, ou None."""
        ...


@dataclass(frozen=True)
class ResolvedMedia:
    """Ce qu'on passe à l'inference, et comment on y est arrivé.

    Attributes:
        value: Un chemin, une URL, ou une data-URI — les trois formes que l'endpoint accepte.
        carried_bytes: Vrai si les octets ont traversé ce processus. C'est le coût qu'on
            cherche à éviter, donc celui qu'il faut pouvoir compter.
        reason: Pourquoi cette forme, pour qu'un log dise quelque chose d'utile.
    """

    value: str
    carried_bytes: bool
    reason: str


class MediaResolver:
    """Traduit une référence média en ce que l'inference sait lire.

    Attributes:
        media_root: La racine des médias telle que ce worker la voit.
        inference_media_root: La même racine, telle que l'inference la voit. Les deux
            diffèrent dès que les deux process ne montent pas le stockage au même endroit.
    """

    def __init__(self, media_root: str, inference_media_root: str) -> None:
        """Lier un résolveur aux deux vues du même stockage."""
        self.media_root = media_root.rstrip("/")
        self.inference_media_root = inference_media_root.rstrip("/")

    def resolve(self, source: MediaSource, table_name: str, view: Any) -> ResolvedMedia | None:
        """Désigner un média pour l'inference.

        L'ordre est une préférence : ce qui évite de transporter des octets vient d'abord.

        Args:
            source: De quoi lire un média embarqué.
            table_name: La table de la vue, pour aller chercher ses octets.
            view: La ligne de vue — elle porte `uri` ou `raw_bytes`, jamais les deux.

        Returns:
            De quoi appeler l'inference, ou None si ce média est introuvable.
        """
        uri = (getattr(view, "uri", "") or "").strip()

        if uri.startswith(REMOTE_SCHEMES):
            return ResolvedMedia(uri, carried_bytes=False, reason="URL que l'inference sait lire")

        if uri:
            translated = self.translate(uri)
            if translated is not None:
                return ResolvedMedia(translated, carried_bytes=False, reason="chemin sous la racine déclarée")
            # Hors des racines déclarées, l'inference refuserait le chemin. Les octets sont la
            # seule route restante, et le log dit pourquoi on la prend.
            logger.debug("média %s hors de %s : envoi des octets", uri, self.media_root)

        return self._inline(source, table_name, view, uri)

    def translate(self, path: str) -> str | None:
        """Passer d'un chemin vu par le worker à un chemin vu par l'inference.

        Returns:
            Le chemin traduit, ou None si ce chemin n'est pas sous la racine déclarée — auquel
            cas l'inference le refuserait, et mieux vaut le savoir ici.
        """
        clean = PurePosixPath(path)
        root = PurePosixPath(self.media_root)
        if not clean.is_absolute() or not clean.is_relative_to(root):
            return None
        return str(PurePosixPath(self.inference_media_root) / clean.relative_to(root))

    def _inline(self, source: MediaSource, table_name: str, view: Any, uri: str) -> ResolvedMedia | None:
        """Aller chercher les octets du média et les encoder.

        C'est la route des datasets importés en mode `embed`, dont les images vivent dans
        LanceDB. Elle coûte cher sur un gros dataset, et c'est pour cela qu'elle est dernière —
        mais elle est indispensable : sans elle, les datasets en place ne seraient pas
        traitables du tout.
        """
        found = source.get_view_binary(table_name, view.id)
        if found is None or not found[0]:
            return None
        reason = "octets embarqués" if not uri else "chemin hors racine, octets envoyés"
        return ResolvedMedia(bytes_to_data_uri(found[0]), carried_bytes=True, reason=reason)
