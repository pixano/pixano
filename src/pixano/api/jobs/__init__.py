# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Submission of processing jobs to the queue shared with pixano-worker."""

from . import queries
from .enqueue import (
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
