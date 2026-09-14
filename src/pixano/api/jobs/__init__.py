# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Submission of processing jobs to the queue shared with pixano-worker."""

from .enqueue import (
    DEFAULT_CHUNK_SIZE,
    JobNotFoundError,
    JobRecord,
    QueueUnavailableError,
    cancel,
    connect,
    enqueue,
    get,
    list_jobs,
    plan_chunks,
    select_record_ids,
)
from .queries import SCHEMA_NAME


__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "SCHEMA_NAME",
    "JobNotFoundError",
    "JobRecord",
    "QueueUnavailableError",
    "cancel",
    "connect",
    "enqueue",
    "get",
    "list_jobs",
    "plan_chunks",
    "select_record_ids",
]
