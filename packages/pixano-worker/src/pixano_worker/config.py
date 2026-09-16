# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Configuration du worker, lue depuis l'environnement.

Le worker ne suppose jamais où tournent ses dépendances : il ne connaît que des adresses.
C'est ce qui permet au même binaire de tourner dans le compose local, à côté d'un NAS et
d'un serveur GPU en mode labo, ou dans le cloud — sans modification de code.

Les variables sans valeur par défaut sont obligatoires : un défaut qui ne vaut qu'en local
ne provoque pas d'erreur au démarrage, il connecte silencieusement le worker au mauvais
endroit et échoue trois couches plus loin.
"""

import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


# Fichier éphémère, propre au conteneur : sa date de modification est la sonde de vivacité.
_HEARTBEAT_PATH_DEFAULT = "/tmp/pixano-worker.heartbeat"  # noqa: S108

# Âge au-delà duquel un worker est considéré mort. Le worker doit battre plus souvent que
# cela quoi qu'il fasse : voir MAX_BACKOFF_S, qui en dérive.
MAX_HEARTBEAT_AGE_S = 30.0


# Chunks exécutés à la fois par défaut. Le temps d'un chunk se passe surtout à attendre
# l'inférence, donc plusieurs chunks en vol remplissent un serveur qu'un seul laisserait
# presque vide. Quatre est un point de départ prudent, pas une mesure : la bonne valeur dépend
# du serveur d'inférence que ce worker partage, et se règle par déploiement.
DEFAULT_CONCURRENCY = 4


def heartbeat_path() -> str:
    """Emplacement du fichier de battement, partagé par le worker et sa sonde."""
    return os.environ.get("PIXANO_WORKER_HEARTBEAT", _HEARTBEAT_PATH_DEFAULT)


class MissingConfigurationError(RuntimeError):
    """Une variable d'environnement obligatoire est absente ou vide."""


def _required(name: str, hint: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingConfigurationError(f"{name} est obligatoire — {hint}")
    return value


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise MissingConfigurationError(f"{name} doit être un entier strictement positif, reçu « {raw} »")
    return value


# psycopg accepte deux écritures : l'URL (postgresql://...) et la forme mot-clé de libpq
# (host=... password=...). Les deux doivent être masquées, sinon un mot de passe finit en
# clair dans les logs le jour où quelqu'un configure la seconde.
_KEYWORD_PASSWORD = re.compile(r"(?i)\bpassword\s*=\s*(?:'(?:[^'\\]|\\.)*'|\S+)")


def redact_dsn(dsn: str) -> str:
    """Remplacer le mot de passe d'une chaîne de connexion par des astérisques."""
    parts = urlsplit(dsn)
    if parts.password is not None:
        user = f"{parts.username}:***" if parts.username else "***"
        port = f":{parts.port}" if parts.port else ""
        return urlunsplit(parts._replace(netloc=f"{user}@{parts.hostname or ''}{port}"))
    return _KEYWORD_PASSWORD.sub("password=***", dsn)


@dataclass(frozen=True)
class WorkerConfig:
    """Tout ce que le worker doit connaître de son environnement de déploiement.

    Attributes:
        database_url: URL de connexion PostgreSQL — file de jobs, état et événements.
        inference_url: URL du serveur pixano-inference.
        inference_api_key: Clé d'API de l'inference. Vide quand elle n'est pas protégée.
        library_dir: Répertoire de la bibliothèque LanceDB, vu par le worker.
        media_root: Racine des médias telle que le worker la voit.
        inference_media_root: La même racine, telle que l'inference la voit. Le worker
            traduit de l'une vers l'autre avant chaque appel : les deux côtés ne montent
            pas nécessairement le même stockage au même endroit.
        heartbeat_path: Fichier dont la fraîcheur sert de sonde de vivacité.
        concurrency: Nombre de chunks exécutés à la fois.
    """

    database_url: str
    inference_url: str
    inference_api_key: str
    library_dir: str
    media_root: str
    inference_media_root: str
    heartbeat_path: str
    concurrency: int = DEFAULT_CONCURRENCY

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        """Construire la configuration depuis l'environnement, ou échouer clairement."""
        return cls(
            database_url=_required("PIXANO_DATABASE_URL", "URL de connexion PostgreSQL"),
            inference_url=_required("PIXANO_INFERENCE_URL", "adresse du serveur pixano-inference"),
            inference_api_key=os.environ.get("PIXANO_INFERENCE_API_KEY", ""),
            library_dir=_required("PIXANO_LIBRARY_DIR", "répertoire de la bibliothèque LanceDB"),
            media_root=_required("PIXANO_MEDIA_ROOT", "racine des médias vue par le worker"),
            inference_media_root=_required("PIXANO_INFERENCE_MEDIA_ROOT", "racine des médias vue par l'inference"),
            heartbeat_path=heartbeat_path(),
            concurrency=_positive_int("PIXANO_WORKER_CONCURRENCY", DEFAULT_CONCURRENCY),
        )

    def describe(self) -> str:
        """Rendre la configuration lisible dans les logs, sans divulguer de secret."""
        lines = [
            f"  base de données   : {redact_dsn(self.database_url)}",
            f"  inference         : {self.inference_url}"
            + (" (authentifiée)" if self.inference_api_key else " (sans clé d'API)"),
            f"  bibliothèque      : {self.library_dir}",
            f"  médias (worker)   : {self.media_root}",
            f"  médias (inference): {self.inference_media_root}",
            f"  concurrence       : {self.concurrency} chunk(s) à la fois",
        ]
        return "\n".join(lines)
