# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Les threads où tourne le code des types de jobs.

Un pool dédié plutôt que celui d'asyncio, pour une raison précise : un thread ne s'interrompt
pas de l'extérieur. Un chunk qui dépasse sa durée est rendu à la file, mais son thread continue
jusqu'à ce que l'appel bloqué revienne — peut-être jamais. Dans le pool par défaut d'asyncio,
ces threads s'accumulent sans que rien ne le voie, jusqu'à ce que plus aucun travail ne puisse
démarrer, planification comprise ; et le battement, qui tourne sur la boucle d'événements,
continue de dire que le worker va bien.

Ici, les threads bloqués sont comptés. Passé un seuil, le pool se déclare saturé, et le worker
s'arrête plutôt que de rester vivant sans rien pouvoir faire : relancé, il repart avec des
threads neufs et reprend ses chunks.
"""

import asyncio
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, TypeVar


T = TypeVar("T")


class WorkerSaturatedError(RuntimeError):
    """Trop de threads sont bloqués pour que le worker puisse encore travailler."""


class WorkerThreads:
    """Un pool borné, qui sait combien de ses threads sont bloqués.

    Attributes:
        stuck_limit: Nombre de threads bloqués à partir duquel le pool est saturé.
    """

    def __init__(self, workers: int, stuck_limit: int) -> None:
        """Créer le pool.

        Args:
            workers: Nombre de threads. Il doit dépasser `stuck_limit` : c'est ce qui laisse au
                worker de quoi constater la saturation avant d'être entièrement bloqué.
            stuck_limit: Nombre de threads bloqués qui rend le pool saturé.

        Raises:
            ValueError: Le pool n'a pas plus de threads que le seuil de saturation.
        """
        if workers <= stuck_limit:
            raise ValueError(f"{workers} thread(s) pour un seuil de saturation de {stuck_limit}")
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pixano-job")
        self.stuck_limit = stuck_limit
        self._stuck = 0
        self._lock = threading.Lock()

    @classmethod
    def for_concurrency(cls, concurrency: int) -> "WorkerThreads":
        """Dimensionner le pool pour un nombre de chunks en vol.

        Un thread par chunk en vol, un pour la planification, et autant de réserve que de
        chunks : saturé quand autant de threads sont bloqués qu'il y a de chunks en vol, le
        pool peut encore servir toute la concurrence au moment où il le signale.
        """
        return cls(workers=2 * concurrency + 1, stuck_limit=concurrency)

    @property
    def stuck(self) -> int:
        """Threads encore occupés par un travail dont on a cessé d'attendre le résultat."""
        with self._lock:
            return self._stuck

    @property
    def saturated(self) -> bool:
        """Le pool a trop de threads bloqués pour que le worker continue."""
        return self.stuck >= self.stuck_limit

    async def run(self, work: Callable[[], T], timeout_s: float | None = None) -> T:
        """Exécuter `work` dans un thread du pool, en attendant au plus `timeout_s`.

        Raises:
            TimeoutError: Le délai est dépassé. Le thread, s'il avait commencé, continue et est
                compté comme bloqué jusqu'à ce qu'il finisse.
        """
        future = self._executor.submit(work)
        try:
            return await asyncio.wait_for(asyncio.wrap_future(future), timeout_s)
        except TimeoutError:
            # Un travail encore en file est annulé pour de bon et ne bloque rien ; seul un travail
            # déjà commencé laisse un thread derrière lui.
            if not future.cancelled():
                self._count_stuck(future)
            raise

    def _count_stuck(self, future: Future) -> None:
        with self._lock:
            self._stuck += 1

        def release(_: Future) -> None:
            with self._lock:
                self._stuck -= 1

        future.add_done_callback(release)

    def shutdown(self) -> None:
        """Libérer le pool sans attendre les threads bloqués."""
        self._executor.shutdown(wait=False, cancel_futures=True)
