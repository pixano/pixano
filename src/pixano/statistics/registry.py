# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The library's registry of statistics: composed once, offered on every dataset they apply to.

The registry is a LanceDB table, `statistic_definitions`, kept beside the datasets in a folder of
the library that is not a dataset (`.pixano`): the library listing skips the folders whose name
starts with a dot. One row per statistic, its choices stored as JSON so that a new choice does not
change the table's columns.

Only the application reads and writes it, from one process: a lock keeps two of its requests from
adding a statistic at once, not two processes. No job computes statistics yet; the one that will is
to receive their definitions in its parameters (backend-processing §22), so that the worker never
opens the registry and a job replayed computes what it was submitted with, whatever the registry
became meanwhile.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path

import lancedb
import pyarrow as pa
from pydantic import ValidationError
from s3path import S3Path

from .definitions import MAX_COLUMN_NAME_LENGTH, StatisticChoices, StatisticDefinition, StatisticLevel


logger = logging.getLogger(__name__)

#: The library's folder that holds what belongs to no single dataset.
LIBRARY_STORE_DIR = ".pixano"

#: The registry's table.
DEFINITIONS_TABLE = "statistic_definitions"

#: The length of the hash that tells apart two statistics whose choices make the same name.
_NAME_SUFFIX_LENGTH = 8

_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string(), nullable=False),
        pa.field("name", pa.string(), nullable=False),
        pa.field("level", pa.string(), nullable=False),
        pa.field("choices", pa.string(), nullable=False),
        pa.field("label", pa.string(), nullable=False),
        pa.field("description", pa.string(), nullable=False),
        pa.field("unit", pa.string(), nullable=False),
        pa.field("value_type", pa.string(), nullable=False),
        pa.field("version", pa.int64(), nullable=False),
        pa.field("created_at", pa.timestamp("us", tz="UTC"), nullable=False),
    ]
)


class StatisticRegistry:
    """The statistics of a library."""

    def __init__(self, library_dir: Path | S3Path) -> None:
        """Open the registry of a library, whose table comes with the first statistic added.

        Args:
            library_dir: The library's folder, local or on S3. On S3, LanceDB reaches the registry by
                its URI, with the credentials of the environment.
        """
        self._store_dir = library_dir / LIBRARY_STORE_DIR
        self._db: lancedb.DBConnection | None = None
        # One request at a time adds a statistic: two adding the same one at once would both find
        # it absent, and both insert it.
        self._adding = threading.Lock()
        # The rows already logged as unreadable: logged once each, not at every read.
        self._unreadable: set[str] = set()

    def definitions(self) -> list[StatisticDefinition]:
        """Every statistic of the library.

        A row that no longer reads as a statistic — one whose choices a later rule refuses — is left
        out and logged rather than failing the whole library. A row stored twice is read once.

        Returns:
            The statistics per record first, then per object, each level by label.
        """
        return self._read(self._rows())

    def _rows(self) -> list[dict[str, object]]:
        """The registry's rows as they are stored, whether they read as statistics or not."""
        table = self._table()
        return [] if table is None else table.to_arrow().to_pylist()

    def _read(self, rows: list[dict[str, object]]) -> list[StatisticDefinition]:
        """The statistics of the registry's rows, each once, the unreadable ones left out."""
        by_id: dict[object, StatisticDefinition] = {}
        for row in rows:
            try:
                definition = _definition_of(row)
            except (ValidationError, ValueError) as error:
                if row.get("id") not in self._unreadable:
                    self._unreadable.add(str(row.get("id")))
                    logger.warning("The library's statistic '%s' cannot be read, left out: %s", row.get("id"), error)
                continue
            kept = by_id.get(row["id"])
            if kept is None or definition.created_at < kept.created_at:
                by_id[row["id"]] = definition
        return sorted(
            by_id.values(), key=lambda definition: (definition.level is not StatisticLevel.RECORD, definition.label)
        )

    def get(self, level: StatisticLevel, name: str) -> StatisticDefinition | None:
        """The library's statistic of this level and name.

        Args:
            level: Its level.
            name: Its name.

        Returns:
            The statistic, or None when the library holds none of this level and name.
        """
        return next(
            (definition for definition in self.definitions() if definition.level is level and definition.name == name),
            None,
        )

    def add(self, definition: StatisticDefinition) -> tuple[StatisticDefinition, bool]:
        """Add a statistic to the library, unless it is there already.

        A statistic of the same choices, computed by the same version of its measure, is the one
        there: it is answered as it was stored, its name and label included. A statistic of other
        choices whose name the library holds already — two values that differ by case alone — gets
        the name ended with a hash of its choices, rather than sharing a column. A name is taken by
        any row, even one that no longer reads as a statistic: its column may hold values still.

        Args:
            definition: The statistic.

        Returns:
            The library's statistic, and whether it was added now.
        """
        with self._adding:
            rows = self._rows()
            stored = self._read(rows)
            same = next(
                (
                    candidate
                    for candidate in stored
                    if candidate.choices == definition.choices and candidate.version == definition.version
                ),
                None,
            )
            if same is not None:
                return same, False
            taken = {str(row["name"]) for row in rows if row.get("level") == definition.level.value}
            if definition.name in taken:
                definition = definition.model_copy(update={"name": _distinct_name(definition, taken)})
            table = self._table()
            if table is None:
                table = self._connection().create_table(DEFINITIONS_TABLE, schema=_SCHEMA, exist_ok=True)
            table.add(pa.Table.from_pylist([_row_of(definition)], schema=_SCHEMA))
            return definition, True

    def _connection(self) -> lancedb.DBConnection:
        if self._db is None:
            uri = self._store_dir.as_uri() if isinstance(self._store_dir, S3Path) else self._store_dir
            self._db = lancedb.connect(uri)
        return self._db

    def _table(self) -> lancedb.table.Table | None:
        """The registry's table, or None while nobody has added a statistic to the library."""
        if not self._store_dir.exists():
            return None
        connection = self._connection()
        if DEFINITIONS_TABLE not in connection.list_tables().tables:
            return None
        return connection.open_table(DEFINITIONS_TABLE)


def _distinct_name(definition: StatisticDefinition, taken: set[str]) -> str:
    """The statistic's name, ended with a hash of its choices, cut to the longest a column name takes.

    A value can be typed to make that very name — `dog_` and the hash of the choices of `dog` —:
    a number then follows the hash, the first one free.
    """
    digest = hashlib.sha256(definition.choices.model_dump_json().encode("utf-8")).hexdigest()[:_NAME_SUFFIX_LENGTH]
    suffix = digest
    attempt = 1
    while True:
        head = definition.name[: MAX_COLUMN_NAME_LENGTH - len(suffix) - 1].rstrip("_")
        name = f"{head}_{suffix}"
        if name not in taken:
            return name
        attempt += 1
        suffix = f"{digest}_{attempt}"


def _row_id(level: StatisticLevel, name: str) -> str:
    return f"{level.value}/{name}"


def _row_of(definition: StatisticDefinition) -> dict[str, object]:
    return {
        "id": _row_id(definition.level, definition.name),
        "name": definition.name,
        "level": definition.level.value,
        "choices": definition.choices.model_dump_json(),
        "label": definition.label,
        "description": definition.description,
        "unit": definition.unit,
        "value_type": definition.value_type,
        "version": definition.version,
        "created_at": definition.created_at,
    }


def _definition_of(row: dict[str, object]) -> StatisticDefinition:
    return StatisticDefinition(
        name=row["name"],
        level=StatisticLevel(row["level"]),
        choices=StatisticChoices.model_validate(json.loads(str(row["choices"]))),
        label=row["label"],
        description=row["description"],
        unit=row["unit"],
        value_type=row["value_type"],
        version=row["version"],
        created_at=row["created_at"],
    )
