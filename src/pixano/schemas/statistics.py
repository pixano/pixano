# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The tables that hold a dataset's statistics: one row per record, and one per object.

A statistic is a column of one of these tables, added the first time it is computed, and nullable:
a record without boxes has no mean box area. Its columns are not fields of these schemas. What a
column holds — the statistic, its unit, the job that computed it — is in the dataset's
`DatasetInfo.statistics`, and its values are read through Arrow (backend-processing §22): a row read
as one of these classes carries its identifiers alone, what every row carries.
"""

from pixano.utils import issubclass_strict

from .records import RecordComponent


class RecordStatistics(RecordComponent):
    """The statistics of a record: its row, whose identifier is the record's."""


class EntityStatistics(RecordComponent):
    """The statistics of an object: its row, whose identifier is the object's.

    Attributes:
        entity_id: The object.
    """

    entity_id: str = ""


def statistics_slot(level: str) -> str:
    """The `DatasetInfo` slot of the statistics table of a level.

    Args:
        level: The level, `record` or `entity`.

    Returns:
        `record_statistics` or `entity_statistics`.
    """
    return f"{level}_statistics"


def is_statistics(cls: type, strict: bool = False) -> bool:
    """Check if a class is a statistics table's schema, of records or of objects."""
    return issubclass_strict(cls, RecordStatistics, strict) or issubclass_strict(cls, EntityStatistics, strict)
