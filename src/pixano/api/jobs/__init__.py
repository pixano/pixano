# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Submission of processing jobs to the queue shared with pixano-worker."""

from . import queries
from .enqueue import (
    DEFAULT_LISTED_JOBS,
    InvalidParamsError,
    JobNotFoundError,
    JobRecord,
    QuarantinedItem,
    QueueUnavailableError,
    UnknownKindError,
    available_kinds,
    cancel,
    check_params,
    connect,
    get,
    list_jobs,
    quarantine,
    submit,
)
from .queries import SCHEMA_NAME


__all__ = [
    "DEFAULT_LISTED_JOBS",
    "SCHEMA_NAME",
    "InvalidParamsError",
    "JobNotFoundError",
    "JobRecord",
    "QuarantinedItem",
    "QueueUnavailableError",
    "UnknownKindError",
    "available_kinds",
    "cancel",
    "check_params",
    "connect",
    "get",
    "list_jobs",
    "quarantine",
    "queries",
    "submit",
]
