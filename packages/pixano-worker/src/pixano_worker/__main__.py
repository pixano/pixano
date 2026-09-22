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

Le démarrage est synchrone — attendre ses dépendances, installer le schéma, déclarer ses
types se fait une fois et dans l'ordre. Seule la boucle de travail est asynchrone.
"""

import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Callable

import httpx
import psycopg
from psycopg_pool import AsyncConnectionPool

from . import queue, runner
from .config import MAX_HEARTBEAT_AGE_S, MissingConfigurationError, WorkerConfig
from .kinds import Registry, default_registry
from .media import MediaResolver
from .schema import SchemaVersionError, ensure_schema
from .threads import WorkerThreads


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("pixano-worker")

# Le worker bat une fois par tour d'attente : l'espacement maximal des tentatives borne donc
# l'âge du battement. Le garder nettement sous MAX_HEARTBEAT_AGE_S évite qu'un worker en
# train d'attendre une dépendance absente soit déclaré mort.
MAX_BACKOFF_S = MAX_HEARTBEAT_AGE_S / 3
IDLE_POLL_INTERVAL_S = 5
CONNECT_TIMEOUT_S = 5

# Le battement ne dépend plus d'un tour de boucle : un chunk long ne doit pas faire déclarer
# mort un worker qui travaille. Ce qu'il prouve désormais, c'est que la boucle d'événements
# n'est pas bloquée. Un chunk pendu, lui, relève de la durée maximale d'un chunk.
HEARTBEAT_INTERVAL_S = MAX_HEARTBEAT_AGE_S / 3


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

    registry = default_registry(config.inference_url, config.inference_api_key, config.demo_kinds)
    worker_id = queue.worker_identity()

    with psycopg.connect(config.database_url, connect_timeout=CONNECT_TIMEOUT_S, autocommit=True) as conn:
        declared = registry.declare(conn, worker_id)
    log.info("worker %s : %d type(s) déclaré(s) — %s", worker_id, declared, ", ".join(registry.names()))

    media = MediaResolver(config.media_root, config.inference_media_root)
    code = asyncio.run(
        serve(
            config.database_url,
            registry,
            worker_id,
            alive,
            Path(config.library_dir),
            media,
            config.concurrency,
            config.chunk_timeout_s,
        )
    )
    # Sans attendre les threads : après un arrêt, certains peuvent rester bloqués sur un appel
    # qui ne revient pas, et une sortie normale les attendrait indéfiniment.
    _exit_now(code)
    return code


def _exit_now(code: int) -> None:
    """Quitter sans attendre les threads.

    Une sortie normale attend que tous les threads aient fini — or certains ne finissent pas.
    Les journaux sont vidés d'abord, pour que le message d'arrêt soit lisible.
    """
    logging.shutdown()
    os._exit(code)


async def serve(
    database_url: str,
    registry: Registry,
    worker_id: str,
    alive: Callable[[], None],
    library: Path,
    media: MediaResolver,
    concurrency: int,
    chunk_timeout_s: float,
) -> int:
    """Battre, puis planifier, exécuter, et récupérer ce que d'autres ont abandonné.

    Returns:
        Le code de sortie : 0 après un arrêt demandé, 1 quand la boucle s'est arrêtée d'elle-même
        sur un défaut persistant — pour que la politique de redémarrage relance un process neuf.
    """
    heartbeat = asyncio.create_task(_beat_forever(alive))
    threads = WorkerThreads.for_concurrency(concurrency)

    # `docker compose stop` envoie SIGTERM. Le worker est le process 1 du conteneur, et le noyau
    # ignore SIGTERM pour un process 1 sans gestionnaire : docker attendait son délai puis tuait
    # le worker, chunks en cours compris.
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)

    # Une connexion par chunk en vol, plus une pour planifier, réclamer et récupérer.
    async with AsyncConnectionPool(
        database_url,
        min_size=1,
        max_size=concurrency + 1,
        kwargs={"autocommit": True, "connect_timeout": CONNECT_TIMEOUT_S},
        # Le pool n'attend pas une connexion plus longtemps qu'on n'attend d'en ouvrir une. Son
        # délai par défaut est de 30 s, subi à chaque emprunt pendant une panne : un arrêt demandé
        # pendant la panne dépassait alors la grâce de docker et finissait tué.
        timeout=CONNECT_TIMEOUT_S,
        # Vérifier une connexion avant de la prêter : après un redémarrage de PostgreSQL, le pool
        # garde des connexions mortes, et sans vérification il les rendrait une à une à la boucle.
        check=AsyncConnectionPool.check_connection,
        open=False,
    ) as pool:
        async with pool.connection() as conn:
            # Ce que cette même identité a laissé derrière elle lors d'un arrêt brutal. Le bail
            # finirait par les libérer ; les rendre tout de suite évite d'attendre son expiration.
            recovery = await queue.release_own(conn, worker_id)
            await runner.settle_abandoned(conn, recovery)
        if recovery.requeued:
            log.info("%d chunk(s) repris d'une exécution précédente", recovery.requeued)
        if recovery.abandoned_jobs:
            log.warning(
                "%d job(s) avec un chunk écarté : il a fait tomber ce worker à chacune de ses tentatives",
                len(recovery.abandoned_jobs),
            )

        log.info("worker démarré, en attente de jobs")
        code = 0
        try:
            try:
                await runner.work(
                    pool,
                    registry,
                    worker_id,
                    concurrency,
                    library,
                    media,
                    IDLE_POLL_INTERVAL_S,
                    chunk_timeout_s,
                    threads,
                    stop,
                )
            except runner.PersistentFailure as error:
                log.error("%s — arrêt en erreur, un worker neuf reprendra", error)
                code = 1
            # Arrêt demandé, ou arrêt sur défaut persistant : même remise en ordre. Ce qui tourne
            # encore est rendu tout de suite : attendre l'expiration du bail coûterait deux
            # minutes, et le prochain worker n'aura peut-être pas la même identité pour les
            # reprendre au démarrage.
            try:
                async with pool.connection() as conn:
                    handed_back = await queue.release_own(conn, worker_id)
                    await runner.settle_abandoned(conn, handed_back)
                log.info("worker arrêté, %d chunk(s) rendu(s) à la file", handed_back.requeued)
            except runner.DATABASE_UNAVAILABLE as error:
                # Arrêté pendant une panne de base : les chunks en cours reviendront par leur bail.
                log.warning(
                    "worker arrêté, base injoignable (%s) — les chunks en cours reviendront par leur bail", error
                )
        finally:
            heartbeat.cancel()
            threads.shutdown()
    return code


async def _beat_forever(alive: Callable[[], None]) -> None:
    while True:
        alive()
        await asyncio.sleep(HEARTBEAT_INTERVAL_S)


if __name__ == "__main__":
    sys.exit(main())
