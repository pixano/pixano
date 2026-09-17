# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Sonde de vivacité du worker, appelée par docker.

Le worker n'expose pas de port : on ne peut pas l'interroger. Une tâche dédiée touche un
fichier à intervalle régulier, et la sonde vérifie que ce battement est récent.

Ce que le battement prouve est précis : la boucle d'événements n'est pas bloquée. Il ne dit
rien d'un chunk pendu dans un appel qui ne revient pas — celui-là tourne dans un thread, et
c'est la durée maximale d'un chunk qui le rend, puis la saturation du pool de threads qui
arrête le worker s'ils s'accumulent.
"""

import os
import sys
import time

from .config import MAX_HEARTBEAT_AGE_S, heartbeat_path


def main() -> int:
    """Renvoyer 0 si le dernier battement est récent, 1 sinon."""
    path = heartbeat_path()
    try:
        age = time.time() - os.path.getmtime(path)
    except OSError:
        print(f"aucun battement à {path}", file=sys.stderr)
        return 1
    if age > MAX_HEARTBEAT_AGE_S:
        print(f"dernier battement il y a {age:.0f}s (> {MAX_HEARTBEAT_AGE_S:.0f}s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
