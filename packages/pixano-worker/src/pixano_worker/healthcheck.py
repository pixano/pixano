# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Liveness probe of the worker, called by docker.

The worker exposes no port: it cannot be queried. A dedicated task touches a file at a
regular interval, and the probe checks that this heartbeat is recent.

What the heartbeat proves is precise: the event loop is not blocked. It says nothing about a
chunk hung in a call that never returns — that one runs in a thread, and it is the maximum
duration of a chunk that hands it back, then the saturation of the thread pool that stops the
worker if they pile up.
"""

import os
import sys
import time

from .config import MAX_HEARTBEAT_AGE_S, heartbeat_path


def main() -> int:
    """Return 0 if the last heartbeat is recent, 1 otherwise."""
    path = heartbeat_path()
    try:
        age = time.time() - os.path.getmtime(path)
    except OSError:
        print(f"no heartbeat at {path}", file=sys.stderr)
        return 1
    if age > MAX_HEARTBEAT_AGE_S:
        print(f"last heartbeat {age:.0f}s ago (> {MAX_HEARTBEAT_AGE_S:.0f}s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
