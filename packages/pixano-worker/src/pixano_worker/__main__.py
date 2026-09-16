# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Point d'entrée du worker Pixano.

Le worker attend ses dépendances, puis boucle. Il ne partage rien avec l'API : ni process,
ni mémoire, ni système de fichiers — tout passe par PostgreSQL. C'est ce qui lui permet de
tourner sur une autre machine que l'application, ce qui est la situation normale dès qu'on
sort du mode local.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Callable

import httpx
import psycopg

from . import queue, runner
from .config import MAX_HEARTBEAT_AGE_S, MissingConfigurationError, WorkerConfig
from .kinds import default_registry
from .media import MediaResolver
from .schema import SchemaVersionError, ensure_schema


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("pixano-worker")

# Le worker bat une fois par tour d'attente : l'espacement maximal des tentatives borne donc
# l'âge du battement. Le garder nettement sous MAX_HEARTBEAT_AGE_S évite qu'un worker en
# train d'attendre une dépendance absente soit déclaré mort.
MAX_BACKOFF_S = MAX_HEARTBEAT_AGE_S / 3
IDLE_POLL_INTERVAL_S = 5
CONNECT_TIMEOUT_S = 5

# Nombre de chunks réclamés d'un coup. Assez pour amortir l'aller-retour en base, assez peu
# pour que l'annulation soit vue rapidement — elle ne se regarde qu'entre deux lots.
BATCH_SIZE = 8


def _wait_for(label: str, probe: Callable[[], None], on_attempt: Callable[[], None]) -> None:
    """Réessayer une sonde jusqu'à ce qu'elle passe, en espaçant les tentatives.

    `on_attempt` est appelé à chaque tour : un worker qui attend une dépendance absente est
    vivant et fait son travail, il ne doit pas être déclaré mort par la sonde de docker. La
    dépendance manquante se voit sur le service concerné, pas ici.
    """
    backoff = 1.0
    while True:
        on_attempt()
        try:
            probe()
            log.info("%s : disponible", label)
            return
        except Exception as exc:
            log.warning(
                "%s : indisponible (%s: %s) — nouvel essai dans %ss", label, exc.__class__.__name__, exc, backoff
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_S)


def wait_for_database(database_url: str, on_attempt: Callable[[], None]) -> None:
    """Attendre que PostgreSQL accepte une connexion."""

    def probe() -> None:
        with psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT_S) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")

    _wait_for("postgresql", probe, on_attempt)


def wait_for_inference(inference_url: str, api_key: str, on_attempt: Callable[[], None]) -> None:
    """Attendre que le serveur d'inférence réponde sur /health."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def probe() -> None:
        httpx.get(f"{inference_url.rstrip('/')}/health", headers=headers, timeout=3).raise_for_status()

    _wait_for("pixano-inference", probe, on_attempt)


def beat(heartbeat_path: str) -> None:
    """Marquer le worker vivant pour la sonde de docker.

    Ouvrir le fichier en écriture suffit : c'est sa date de modification que la sonde lit.
    """
    with open(heartbeat_path, "w"):
        pass


def main() -> int:
    """Démarrer le worker."""
    try:
        config = WorkerConfig.from_env()
    except MissingConfigurationError as exc:
        log.error("configuration incomplète : %s", exc)
        return 1

    log.info("configuration du worker :\n%s", config.describe())

    def alive() -> None:
        beat(config.heartbeat_path)

    alive()
    wait_for_database(config.database_url, alive)

    # Le schéma se vérifie avant d'attendre l'inference : un schéma incompatible est fatal,
    # et l'opérateur doit l'apprendre en deux secondes, pas après cinq minutes d'attente
    # polie d'un serveur dont ce worker ne se servira jamais.
    try:
        with psycopg.connect(config.database_url, connect_timeout=CONNECT_TIMEOUT_S) as conn:
            ensure_schema(conn)
    except SchemaVersionError as exc:
        log.error("%s", exc)
        return 1
    except psycopg.Error as exc:
        log.error("impossible d'installer le schéma : %s", exc)
        return 1

    alive()
    wait_for_inference(config.inference_url, config.inference_api_key, alive)

    registry = default_registry()
    worker_id = queue.worker_identity()

    with psycopg.connect(config.database_url, connect_timeout=CONNECT_TIMEOUT_S, autocommit=True) as conn:
        declared = registry.declare(conn, worker_id)
        log.info("worker %s : %d type(s) déclaré(s) — %s", worker_id, declared, ", ".join(registry.names()))

        # Ce que cette même identité a laissé derrière elle lors d'un arrêt brutal. Le bail
        # finirait par les libérer ; les rendre tout de suite évite d'attendre son expiration.
        recovered = queue.release_own(conn, worker_id)
        if recovered:
            log.info("%d chunk(s) repris d'une exécution précédente", recovered)

        log.info("worker démarré, en attente de jobs")
        media = MediaResolver(config.media_root, config.inference_media_root)
        _work_forever(conn, registry, worker_id, alive, Path(config.library_dir), media)
    return 0


def _work_forever(conn, registry, worker_id: str, alive, library: Path, media: MediaResolver) -> None:
    """Planifier, exécuter, et récupérer ce que d'autres ont abandonné."""
    while True:
        alive()
        planned = runner.plan_one(conn, registry, library, media)
        processed = runner.run_batch(conn, registry, worker_id, BATCH_SIZE, library)
        if planned is None and processed == 0:
            reclaimed, abandoned = queue.reclaim_expired(conn)
            if reclaimed or abandoned:
                log.info("baux expirés : %d chunk(s) remis en file, %d écarté(s)", reclaimed, abandoned)
            time.sleep(IDLE_POLL_INTERVAL_S)


if __name__ == "__main__":
    sys.exit(main())
