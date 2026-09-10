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
from typing import Callable

import httpx
import psycopg

from .config import MAX_HEARTBEAT_AGE_S, MissingConfigurationError, WorkerConfig


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("pixano-worker")

# Le worker bat une fois par tour d'attente : l'espacement maximal des tentatives borne donc
# l'âge du battement. Le garder nettement sous MAX_HEARTBEAT_AGE_S évite qu'un worker en
# train d'attendre une dépendance absente soit déclaré mort.
MAX_BACKOFF_S = MAX_HEARTBEAT_AGE_S / 3
IDLE_POLL_INTERVAL_S = 5


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
        with psycopg.connect(database_url, connect_timeout=3) as conn, conn.cursor() as cur:
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
    wait_for_inference(config.inference_url, config.inference_api_key, alive)

    log.info("worker démarré, en attente de jobs")
    while True:
        # TODO lot 2 : réclamer un lot de chunks (SELECT ... FOR UPDATE SKIP LOCKED).
        alive()
        time.sleep(IDLE_POLL_INTERVAL_S)


if __name__ == "__main__":
    sys.exit(main())
