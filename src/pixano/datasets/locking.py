# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Cooperative, process-safe exclusion for local dataset mutations."""

from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from uuid import uuid4

from filelock import FileLock, Timeout
from s3path import S3Path

from .utils.errors import DatasetBusyError


@contextmanager
def dataset_mutation_lock(path: Path, *, timeout: float = 0):
    """Acquire a reentrant dataset lock, failing immediately by default.

    The lock lives outside the dataset so replacing the directory cannot replace
    its lock inode. Staging locks live outside staging for the same reason.
    Storage upgrades may wait briefly for another opener via ``timeout``.
    """
    # Add/rollback jobs are local-only. Preserve existing remote Dataset access
    # without coercing an S3 bucket key into a local filesystem path. This lock
    # makes no distributed-locking guarantee for remote storage.
    if isinstance(path, S3Path):
        yield
        return
    path = Path(path).resolve()
    lock_path = path.parent / f".{path.name}.pixano-write.lock"
    if path.parent.name == "staging" and path.parent.parent.name == ".pixano":
        lock_path = path.parent.parent / "locks" / f"{path.name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(lock_path), timeout=0, thread_local=True, is_singleton=True)
    try:
        lock.acquire(timeout=timeout)
    except Timeout as error:
        raise DatasetBusyError("Dataset is being modified; retry when the current operation finishes.") from error
    try:
        yield
    finally:
        lock.release()


def mutation_token(path: Path) -> str:
    """Read the last cooperative mutation identity (empty for legacy datasets)."""
    if isinstance(path, S3Path):
        return ""
    marker = Path(path) / ".pixano-mutation"
    return marker.read_text(encoding="utf-8") if marker.is_file() else ""


def mark_dataset_mutated(path: Path) -> None:
    """Invalidate older rollback anchors before a write; caller must hold the lock."""
    if isinstance(path, S3Path):
        return
    marker = Path(path) / ".pixano-mutation"
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(uuid4().hex, encoding="utf-8")
    temporary.replace(marker)


def dataset_write(method):
    """Protect a Dataset mutation, including its integrity reads and metadata writes."""

    @wraps(method)
    def locked(self, *args, **kwargs):
        with self.write_lock():
            mark_dataset_mutated(self.path)
            return method(self, *args, **kwargs)

    return locked
