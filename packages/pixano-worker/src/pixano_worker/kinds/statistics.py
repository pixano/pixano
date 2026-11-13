# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A job kind that computes statistics on a dataset, per record and per object (backend-processing §22).

The statistics are those a person composed and chose to compute: the job receives their definitions
in its parameters, and computes them as they were composed, whatever the library's became since. It
calls no inference: a chunk is a batch of records, whose objects and annotations it reads, measures
and writes back as the values of one column per statistic.

A replay writes the same values over the same rows: a row's identifier is its record's, or its
object's. Only the job's columns are written, so that the other statistics of a row keep theirs.
Once every chunk is done, the dataset records what the job computed, which the explorer names its
columns after.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from pixano.datasets.statistic_choices import statistic_applies
from pixano.schemas.table_names import canonical_table_name_for_slot
from pixano.statistics.compute import RecordContent, compute_values, drawn_on
from pixano.statistics.definitions import (
    BOX_ELEMENT,
    ENTITY_ELEMENT,
    MASK_ELEMENT,
    StatisticDefinition,
    StatisticLevel,
    StatisticMeasure,
)
from pixano.utils.python import IDS_PER_QUERY, to_sql_list

from ..reader import JobReader
from ..writer import JobWriter, columns_by_level
from .base import OWN_FORM_MARKER, Chunk, JobKind, JobParams


#: Records per chunk. A chunk reads its records' annotations and writes one row each, with no
#: inference to wait for: large, so that a dataset takes few writes. At most the identifiers one
#: query names, as a chunk's records are read in one query per table.
DEFAULT_CHUNK_SIZE = 500
MAX_CHUNK_SIZE = IDS_PER_QUERY

#: The most statistics one job computes. Each is a column, read and written by every chunk.
MAX_STATISTICS_PER_JOB = 50

#: The media whose views have a size in pixels a box is measured against: images, and the frames
#: of a video.
_SIZED_MEDIA = ("image", "video")

#: The table of a dataset's objects.
_ENTITY_TABLE = canonical_table_name_for_slot("entity")


class StatisticsParams(JobParams):
    """Parameters of the statistics job.

    The application submits it with the definitions of the statistics to compute, which the
    generic form cannot build (`OWN_FORM_MARKER`).

    Attributes:
        statistics: The statistics to compute, as they were composed.
        chunk_size: Records per chunk.
    """

    model_config = ConfigDict(json_schema_extra={OWN_FORM_MARKER: "statistics"})

    statistics: list[StatisticDefinition] = Field(min_length=1, max_length=MAX_STATISTICS_PER_JOB)
    chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, ge=1, le=MAX_CHUNK_SIZE)

    @field_validator("statistics")
    @classmethod
    def _each_once(cls, statistics: list[StatisticDefinition]) -> list[StatisticDefinition]:
        """Refuse a statistic asked twice: two definitions would write one column."""
        keys = [(statistic.level, statistic.name) for statistic in statistics]
        if len(set(keys)) != len(keys):
            raise ValueError("A statistic is asked for twice.")
        return statistics


class StatisticsKind(JobKind[StatisticsParams]):
    """Computes, per record and per object, the statistics a person composed."""

    name = "statistics"
    params_model = StatisticsParams
    # A count or an area measured by a rule is not a model's prediction.
    source_type = "other"

    def plan(self, reader: JobReader, params: StatisticsParams) -> Iterable[Chunk]:
        """Split the records into chunks, once every statistic is known to be computable as composed.

        Raises:
            ValueError: A statistic's measure is computed otherwise since it was composed, its values
                would land in the column of the previous computation; or it measures a mask's area or
                its share of its image, not measured yet; or it measures what the dataset does not
                hold, or filters on an attribute its objects lack — named in the message.
        """
        _refuse_outdated(params.statistics)
        _refuse_mask_areas(params.statistics)
        inapplicable = [
            statistic.label
            for statistic in params.statistics
            if not statistic_applies(statistic.choices, reader.dataset)
        ]
        if inapplicable:
            raise ValueError(
                f"the dataset does not hold what these statistics measure or filter on: {', '.join(inapplicable)}."
            )
        batch: list[str] = []
        for record_id in reader.ids("records"):
            batch.append(record_id)
            if len(batch) == params.chunk_size:
                yield Chunk(payload={"record_ids": batch}, task_count=len(batch))
                batch = []
        if batch:
            yield Chunk(payload={"record_ids": batch}, task_count=len(batch))

    def prepare(self, writer: JobWriter, params: StatisticsParams) -> None:
        """Give the dataset the tables and columns of the statistics, empty where they are new."""
        writer.ensure_statistics(params.statistics)

    def process(self, reader: JobReader, payload: dict[str, Any], params: StatisticsParams) -> dict[str, Any]:
        """Measure each record of the chunk, and each of its objects.

        Raises:
            ValueError: A statistic's measure is computed otherwise since the job was planned: a
                worker updated in between would write the new computation into the old column. Or it
                measures a mask's area, which the worker that planned the job may measure and this
                one does not.
        """
        _refuse_outdated(params.statistics)
        _refuse_mask_areas(params.statistics)
        record_ids: list[str] = payload["record_ids"]
        listed = to_sql_list(record_ids)

        entities: dict[str, list[Any]] = {}
        if _needs_objects(params) and _ENTITY_TABLE in reader.dataset.info.tables:
            entities = _by_record(reader.read(_ENTITY_TABLE, f"record_id IN {listed}"))
        annotations = {
            element: _by_record(reader.read(canonical_table_name_for_slot(element), f"record_id IN {listed}"))
            for element in {statistic.choices.element for statistic in params.statistics} - {ENTITY_ELEMENT}
        }
        sizes = None
        if _needs_view_sizes(params.statistics):
            boxes = [box for rows in annotations.get(BOX_ELEMENT, {}).values() for box in rows]
            sizes = _ViewSizes(reader, {drawn_on(box) for box in boxes})

        records: dict[str, dict[str, Any]] = {}
        objects: list[dict[str, Any]] = []
        for record_id in record_ids:
            content = RecordContent(
                record_id=record_id,
                entities=entities.get(record_id, []),
                annotations={element: rows.get(record_id, []) for element, rows in annotations.items()},
                image_size=sizes.of if sizes is not None else _no_size,
                mask_grid=_no_mask_geometry,
            )
            computed = compute_values(params.statistics, content)
            records[record_id] = computed.record
            objects += [
                {"record_id": record_id, "entity_id": entity_id, **values}
                for entity_id, values in computed.entities.items()
            ]
        return {"records": records, "objects": objects}

    def write(
        self, writer: JobWriter, result: dict[str, Any], payload: dict[str, Any], params: StatisticsParams
    ) -> None:
        """Write the values of the chunk's records and objects, in the job's columns only.

        The rows of objects deleted since the last computation go: their record no longer holds
        them, and their values would linger beside the others'.
        """
        writer.ensure_statistics(params.statistics)
        columns = columns_by_level(params.statistics)
        record_columns = columns.get(StatisticLevel.RECORD, {})
        if record_columns:
            writer.write_statistics(
                StatisticLevel.RECORD,
                [{"record_id": record_id, **values} for record_id, values in result["records"].items()],
                record_columns,
            )
        entity_columns = columns.get(StatisticLevel.ENTITY, {})
        if entity_columns:
            # The rows written, not those measured: an object deleted since it was measured is not
            # written, and its previous row goes with the others of objects no longer there.
            written = writer.write_statistics(StatisticLevel.ENTITY, result["objects"], entity_columns)
            writer.forget_object_statistics(payload["record_ids"], kept=set(written))

    def finalize(self, reader: JobReader, writer: JobWriter, params: StatisticsParams) -> None:
        """Record in the dataset what the job computed, so that the explorer names and dates its columns."""
        writer.record_computed_statistics(params.statistics)


def _refuse_mask_areas(statistics: Sequence[StatisticDefinition]) -> None:
    """Refuse a mask's area and its share of its image: the masks' geometry is not read yet.

    Raises:
        ValueError: Some measure them, named in the message.
    """
    unmeasured = [
        statistic.label
        for statistic in statistics
        if statistic.choices.element == MASK_ELEMENT and statistic.choices.measure is not StatisticMeasure.COUNT
    ]
    if unmeasured:
        raise ValueError(f"a mask's area, and its share of its image, are not measured yet: {', '.join(unmeasured)}.")


def _no_mask_geometry(mask: Any) -> None:
    """A mask's grid and painted pixels, never read: planning and every chunk refuse a mask's area."""
    return None


def _refuse_outdated(statistics: Sequence[StatisticDefinition]) -> None:
    """Refuse statistics whose measure is computed otherwise since they were composed.

    Raises:
        ValueError: Some are, named in the message: their values would land in the column of the
            previous computation.
    """
    obsolete = [statistic.label for statistic in statistics if not statistic.is_current]
    if obsolete:
        raise ValueError(
            f"these statistics are computed otherwise since they were composed: {', '.join(obsolete)}. "
            "Compose them again."
        )


def _needs_objects(params: StatisticsParams) -> bool:
    """Whether a statistic reads the objects: one per object, one counting them, or one filtering on
    their attributes.
    """
    return any(
        statistic.level is StatisticLevel.ENTITY
        or statistic.choices.element == ENTITY_ELEMENT
        or statistic.choices.attribute is not None
        for statistic in params.statistics
    )


def _by_record(rows: list[Any]) -> dict[str, list[Any]]:
    """Rows grouped by their record, read once rather than once per record."""
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[row.record_id].append(row)
    return grouped


def _needs_view_sizes(statistics: Sequence[StatisticDefinition]) -> bool:
    """Whether a statistic measures boxes against their view: an area or a share of it."""
    return any(
        statistic.choices.element == BOX_ELEMENT and statistic.choices.measure is not StatisticMeasure.COUNT
        for statistic in statistics
    )


def _no_size(view_id: str) -> tuple[int, int] | None:
    """No statistic of the job needs an image's size."""
    return None


class _ViewSizes:
    """The sizes of the views a chunk's boxes are drawn on — images, and a video's frames — read once
    each, when a box asks for one.

    Only those views are read, by identifier: a video record holds thousands of frames, and a chunk
    hundreds of records.
    """

    def __init__(self, reader: JobReader, view_ids: set[str]) -> None:
        self._reader = reader
        self._view_ids = sorted(view_ids)
        self._views: dict[str, tuple[str, Any]] | None = None
        self._sizes: dict[str, tuple[int, int] | None] = {}

    def of(self, view_id: str) -> tuple[int, int] | None:
        """The width and height of a view, in pixels; None when it is unknown, or not a view."""
        if view_id not in self._sizes:
            if self._views is None:
                self._views = self._read_views()
            found = self._views.get(view_id)
            self._sizes[view_id] = self._reader.image_size(*found) if found is not None else None
        return self._sizes[view_id]

    def _read_views(self) -> dict[str, tuple[str, Any]]:
        """The boxes' views, with their table, from every table of sized media."""
        views: dict[str, tuple[str, Any]] = {}
        for media in _SIZED_MEDIA:
            for table in self._reader.media_tables(media):
                for start in range(0, len(self._view_ids), IDS_PER_QUERY):
                    for view in self._reader.rows(table, self._view_ids[start : start + IDS_PER_QUERY]):
                        views[view.id] = (table, view)
        return views
