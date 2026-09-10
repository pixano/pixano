# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Sonde de vivacité du worker, appelée par docker.

Le worker n'expose pas de port : on ne peut pas l'interroger. Il touche un fichier à chaque
tour de boucle, et la sonde vérifie que ce battement est récent. Un worker bloqué dans un
appel qui ne revient pas est ainsi détecté, là où un simple « le process existe » ne dirait
rien.
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
