# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime

from lancedb.pydantic import LanceModel
from pydantic import Field

from pixano.utils import issubclass_strict


class Record(LanceModel):
    """Record base class.
    Records are top level objects to represent dataset samples.
    They are stored in the main table of the database.

    Attributes:
        id: The record's ID.
        split: The record's split.
        created_at: The record's creation date.
        updated_at: The record's last modification date.
    """

    id: str = ""
    split: str = "default"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class RecordComponent(LanceModel):
    """Record component.
    Record components are used to store all other objects that are part of a record. That cannot be stored in
    the main table of the database. Otherwise, the main table would be too big and have a deep structure.
    Records components are stored in their corresponding auxiliary tables and referenced by the record's id.
    """

    id: str = ""
    record_id: str = ""


def is_record(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `Record` or subclass of `Record`."""
    return issubclass_strict(cls, Record, strict)


def is_record_component(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `RecordComponent` or subclass of `RecordComponent`."""
    return issubclass_strict(cls, RecordComponent, strict)
