# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The import engine: the only component that writes datasets (spec §8).

Responsibilities the format importers never carry:

- byte- and row-bounded buffering of streamed batches;
- integrity at scale via an :class:`~pixano.datasets.io.ids.IdLedger`
  (cross-flush duplicate detection; FK resolution without DB scans on fresh
  builds);
- atomicity: ``create``/``overwrite`` build in ``<data_dir>/.pixano/staging/``
  and atomically rename into ``library/`` (overwrite goes through a journaled
  old→trash→swap sequence replayed on boot); ``add`` writes an
  :class:`~pixano.datasets.io.manifest.ImportManifest` *before* the first
  write and routes every flush through the upserting
  :meth:`~pixano.datasets.dataset.Dataset.merge_records`;
- the media-storage census stamping ``DatasetInfo.storage_mode``;
- scalar indexes, provenance stamps, cache invalidation, and progress events
  at finalize.
"""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Literal, Sequence

import PIL.Image
import pyarrow as pa
import pyarrow.compute as pc
import shortuuid
from lancedb.pydantic import LanceModel

from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.utils.integrity import validate_arrow_batch, validate_batch
from pixano.schemas import SchemaGroup, is_image, is_sequence_frame, is_view, schema_to_group
from pixano.schemas.views.image import _generate_preview
from pixano.utils import to_snake_case

from .errors import JobStateError, SpecValidationError, UnsupportedStorageError
from .ids import IdLedger
from .importer import Cursor, DatasetImporter, SourceRef
from .manifest import ImportManifest
from .plan import ImportPlan
from .progress import ProgressEvent, ProgressSink
from .spec import ImportSpec


logger = logging.getLogger(__name__)

PIXANO_STATE_DIR = ".pixano"
DEFAULT_FLUSH_ROWS = 4096
DEFAULT_FLUSH_BYTES = 256 * 1024 * 1024


@dataclass
class ImportResult:
    """Outcome of one import job."""

    dataset_id: str
    dataset_path: Path
    table_counts: dict[str, int]
    job_id: str
    manifest_path: Path | None
    duration_s: float
    storage_mode: str


class _LedgerTableView:
    """Set-like view over one ledger table for `validate_batch` known_ids checks."""

    def __init__(self, ledger: IdLedger, table: str):
        self._ledger = ledger
        self._table = table

    def __contains__(self, id: object) -> bool:
        return isinstance(id, str) and self._ledger.contains(self._table, id)


class _LedgerKnownIds(Mapping):
    """Mapping façade exposing the ledger as `validate_batch`'s known_ids argument."""

    def __init__(self, ledger: IdLedger, tables: Sequence[str]):
        self._ledger = ledger
        self._tables = list(tables)

    def __getitem__(self, table: str) -> _LedgerTableView:
        return _LedgerTableView(self._ledger, table)

    def get(self, table: str, default: object = None) -> _LedgerTableView:
        return _LedgerTableView(self._ledger, table)

    def __iter__(self):
        return iter(self._tables)

    def __len__(self) -> int:
        return len(self._tables)


def state_dir(data_dir: Path) -> Path:
    """The engine's state directory (staging/trash/journal) — outside library/."""
    return data_dir / PIXANO_STATE_DIR


def replay_journals(data_dir: Path) -> None:
    """Complete interrupted overwrite swaps (idempotent; run at engine and server start)."""
    journal_dir = state_dir(data_dir) / "journal"
    if not journal_dir.is_dir():
        return
    for journal_file in sorted(journal_dir.glob("*.json")):
        try:
            journal = json.loads(journal_file.read_text(encoding="utf-8"))
            target = Path(journal["target"])
            staging = Path(journal["staging"])
            trash = Path(journal["trash"])
            if staging.exists() and not target.exists():
                # Crashed between old→trash and staging→target: finish the swap.
                os.rename(staging, target)
            if target.exists() and trash.exists():
                shutil.rmtree(trash, ignore_errors=True)
            if target.exists() and not staging.exists():
                journal_file.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Could not replay overwrite journal %s: %s", journal_file, exc)


class ImportEngine:
    """Runs one import job end to end (spec §8)."""

    def __init__(
        self,
        data_dir: Path,
        flush_rows: int = DEFAULT_FLUSH_ROWS,
        flush_bytes: int = DEFAULT_FLUSH_BYTES,
        checkpoint: Callable[[Cursor, dict[str, int]], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ):
        """Initialize the engine for a data directory.

        Args:
            data_dir: The Pixano data directory (holds ``library/`` and ``.pixano/``).
            flush_rows: Row threshold triggering a buffer flush.
            flush_bytes: Approximate byte threshold triggering a buffer flush.
            checkpoint: Called after each committed flush with (cursor, table_counts).
            cancel_check: Polled at flush boundaries; True aborts the job.
        """
        if not isinstance(data_dir, Path):
            raise UnsupportedStorageError("Import jobs require a local filesystem data directory.")
        self.data_dir = data_dir
        self.library_dir = data_dir / "library"
        self.flush_rows = flush_rows
        self.flush_bytes = flush_bytes
        self.checkpoint = checkpoint
        self.cancel_check = cancel_check
        self._canaried_tables: set[str] = set()

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(
        self,
        importer: DatasetImporter,
        source: SourceRef,
        spec: ImportSpec,
        plan: ImportPlan,
        info: DatasetInfo,
        sinks: Sequence[ProgressSink] = (),
    ) -> ImportResult:
        """Execute the plan: stream, validate, write, finalize — atomically per mode."""
        started_at = time.monotonic()
        job_id = shortuuid.uuid()
        dataset_name = to_snake_case(spec.dataset.name or info.name)
        if not dataset_name:
            raise SpecValidationError("dataset.name must contain at least one alphanumeric character.")
        target_dir = self.library_dir / dataset_name

        replay_journals(self.data_dir)

        if spec.mode == "add":
            return self._run_add(importer, source, spec, plan, job_id, target_dir, sinks, started_at)
        return self._run_build(importer, source, spec, plan, info, job_id, dataset_name, target_dir, sinks, started_at)

    # ------------------------------------------------------------------
    # create / overwrite: staged build + atomic promotion
    # ------------------------------------------------------------------

    def _run_build(
        self,
        importer: DatasetImporter,
        source: SourceRef,
        spec: ImportSpec,
        plan: ImportPlan,
        info: DatasetInfo,
        job_id: str,
        dataset_name: str,
        target_dir: Path,
        sinks: Sequence[ProgressSink],
        started_at: float,
    ) -> ImportResult:
        if spec.mode == "create" and target_dir.exists():
            raise SpecValidationError(
                f"Dataset '{dataset_name}' already exists at '{target_dir}'. Use mode 'overwrite' or 'add'."
            )

        staging_dir = state_dir(self.data_dir) / "staging" / f"{dataset_name}-{job_id}"
        staging_dir.parent.mkdir(parents=True, exist_ok=True)
        self.library_dir.mkdir(parents=True, exist_ok=True)
        self._assert_same_filesystem(staging_dir.parent, self.library_dir)

        if not info.id:
            info.id = shortuuid.uuid()
        dataset = Dataset.create(staging_dir, info)
        ledger = IdLedger(spill_dir=staging_dir / ".ledger")
        table_counts: dict[str, int] = {}
        census = _MediaCensus()

        try:
            for cursor in self._stream(importer, source, spec, plan, dataset, ledger, table_counts, census, sinks):
                if self.checkpoint is not None:
                    self.checkpoint(cursor, dict(table_counts))
                self._check_cancelled()
            self._finalize(dataset, spec, plan, importer, job_id, table_counts, census, sinks, add_mode=False)
        except BaseException:
            ledger.close()
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise
        ledger.close()
        shutil.rmtree(staging_dir / ".ledger", ignore_errors=True)

        self._promote(staging_dir, target_dir, job_id)
        Dataset.invalidate_caches(dataset.info.id)

        return ImportResult(
            dataset_id=dataset.info.id,
            dataset_path=target_dir,
            table_counts=dict(table_counts),
            job_id=job_id,
            manifest_path=None,
            duration_s=time.monotonic() - started_at,
            storage_mode=dataset.info.storage_mode,
        )

    def _promote(self, staging_dir: Path, target_dir: Path, job_id: str) -> None:
        """Atomically move the staged dataset into the library (journaled for overwrite)."""
        if not target_dir.exists():
            os.rename(staging_dir, target_dir)
            return

        journal_dir = state_dir(self.data_dir) / "journal"
        trash_dir = state_dir(self.data_dir) / "trash" / f"{target_dir.name}-{job_id}"
        trash_dir.parent.mkdir(parents=True, exist_ok=True)
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal_file = journal_dir / f"{job_id}.json"
        journal_file.write_text(
            json.dumps({"target": str(target_dir), "staging": str(staging_dir), "trash": str(trash_dir)}),
            encoding="utf-8",
        )
        os.rename(target_dir, trash_dir)
        os.rename(staging_dir, target_dir)
        shutil.rmtree(trash_dir, ignore_errors=True)
        journal_file.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # add: manifest + upserting flushes
    # ------------------------------------------------------------------

    def _run_add(
        self,
        importer: DatasetImporter,
        source: SourceRef,
        spec: ImportSpec,
        plan: ImportPlan,
        job_id: str,
        target_dir: Path,
        sinks: Sequence[ProgressSink],
        started_at: float,
    ) -> ImportResult:
        if not target_dir.exists():
            raise SpecValidationError(f"Dataset '{target_dir.name}' does not exist; use mode 'create'.")
        dataset = Dataset(target_dir)

        manifest = ImportManifest(
            job_id=job_id,
            dataset_id=dataset.info.id,
            spec_fingerprint=spec.fingerprint(),
            plan_fingerprint=plan.plan_fingerprint,
            id_namespace=spec.ids.namespace or "",
            importer_version=importer.importer_version,
            pre_import_versions={name: dataset.open_table(name).version for name in dataset.info.tables},
        )
        manifest_path = target_dir / "imports" / f"{job_id}.manifest.json"
        manifest.save(manifest_path)

        # Indexes make the upserting merge path scale past full-table scans.
        dataset.create_scalar_indexes()

        ledger = IdLedger()
        table_counts: dict[str, int] = {}
        census = _MediaCensus()
        try:
            for cursor in self._stream(
                importer, source, spec, plan, dataset, ledger, table_counts, census, sinks, add_mode=True
            ):
                if self.checkpoint is not None:
                    self.checkpoint(cursor, dict(table_counts))
                self._check_cancelled()
            self._finalize(dataset, spec, plan, importer, job_id, table_counts, census, sinks, add_mode=True)
        finally:
            ledger.close()

        manifest.post_import_versions = {name: dataset.open_table(name).version for name in dataset.info.tables}
        manifest.save(manifest_path)
        Dataset.invalidate_caches(dataset.info.id)

        return ImportResult(
            dataset_id=dataset.info.id,
            dataset_path=target_dir,
            table_counts=dict(table_counts),
            job_id=job_id,
            manifest_path=manifest_path,
            duration_s=time.monotonic() - started_at,
            storage_mode=dataset.info.storage_mode,
        )

    # ------------------------------------------------------------------
    # Streaming + buffering
    # ------------------------------------------------------------------

    def _stream(
        self,
        importer: DatasetImporter,
        source: SourceRef,
        spec: ImportSpec,
        plan: ImportPlan,
        dataset: Dataset,
        ledger: IdLedger,
        table_counts: dict[str, int],
        census: "_MediaCensus",
        sinks: Sequence[ProgressSink],
        add_mode: bool = False,
    ) -> Iterator[Cursor]:
        """Consume importer bundles through bounded buffers; yield committed cursors."""
        row_buffers: dict[str, list[LanceModel]] = {}
        buffered_rows = 0
        buffered_bytes = 0
        last_cursor: Cursor = {}

        def flush() -> None:
            nonlocal buffered_rows, buffered_bytes
            if not row_buffers:
                return
            self._flush_rows(dataset, row_buffers, ledger, table_counts, census, add_mode)
            row_buffers.clear()
            buffered_rows = 0
            buffered_bytes = 0
            self._emit_progress(sinks, plan, table_counts)

        for bundle in importer.iter_batches(source, spec, plan):
            for table_name, payload in bundle.tables.items():
                if isinstance(payload, (pa.RecordBatch, pa.Table)):
                    # Arrow payloads are pre-batched by the importer: write through.
                    flush()
                    self._flush_arrow(dataset, table_name, payload, ledger, table_counts, census, add_mode)
                    self._emit_progress(sinks, plan, table_counts)
                    continue
                rows = payload if isinstance(payload, list) else [payload]
                if not rows:
                    continue
                row_buffers.setdefault(table_name, []).extend(rows)
                buffered_rows += len(rows)
                buffered_bytes += sum(_approx_row_bytes(row) for row in rows)

            if buffered_rows >= self.flush_rows or buffered_bytes >= self.flush_bytes:
                flush()
                last_cursor = dict(bundle.cursor)
                yield last_cursor

        flush()
        yield dict(last_cursor)

    def _flush_rows(
        self,
        dataset: Dataset,
        buffers: dict[str, list[LanceModel]],
        ledger: IdLedger,
        table_counts: dict[str, int],
        census: "_MediaCensus",
        add_mode: bool,
    ) -> None:
        batch = {table: rows for table, rows in buffers.items() if rows}
        if not batch:
            return
        for table, rows in batch.items():
            _stamp_image_previews(dataset, table, rows)
            census.observe_rows(dataset, table, rows)

        if add_mode:
            # Upsert path: merge_records owns validation with upsert semantics.
            known = None if ledger_spilled(ledger) else ledger.known_ids(list(dataset.info.tables))
            dataset.merge_records(batch, check_integrity="raise", known_ids=known)
        else:
            # Fresh build: the ledger answers uniqueness and FK checks — no DB scans.
            pending_ids = {table: {row.id for row in rows if row.id} for table, rows in batch.items()}
            known_ids = _LedgerKnownIds(ledger, list(dataset.info.tables))
            for table_name in dataset._table_insert_order(list(batch.keys())):
                validate_batch(
                    table_name,
                    batch[table_name],
                    known_ids,  # type: ignore[arg-type]
                    dataset,
                    raise_or_warn="raise",
                    pending_ids=pending_ids,
                    fk_lookup=ledger.fk_lookup,
                )
            dataset.add_records(batch, check_integrity="none")

        for table, rows in batch.items():
            ledger.add(table, [row.id for row in rows if row.id])
            table_counts[table] = table_counts.get(table, 0) + len(rows)

    def _flush_arrow(
        self,
        dataset: Dataset,
        table_name: str,
        payload: pa.RecordBatch | pa.Table,
        ledger: IdLedger,
        table_counts: dict[str, int],
        census: "_MediaCensus",
        add_mode: bool,
    ) -> None:
        arrow_table = pa.Table.from_batches([payload]) if isinstance(payload, pa.RecordBatch) else payload
        if arrow_table.num_rows == 0:
            return
        census.observe_arrow(dataset, table_name, arrow_table)
        ids = [str(id) for id in arrow_table.column("id").to_pylist() if id]

        # First-batch canary: round-trip one row through Pydantic so a mistyped
        # or misnamed column fails on the first flush, not rows later.
        if table_name not in self._canaried_tables:
            self._canaried_tables.add(table_name)
            schema_cls = dataset.info.tables.get(table_name)
            if schema_cls is not None:
                try:
                    schema_cls.model_validate(arrow_table.slice(0, 1).to_pylist()[0])
                except Exception as exc:
                    raise SpecValidationError(
                        f"Arrow batch for table '{table_name}' does not match the schema: {exc}"
                    ) from None

        # Cross-flush duplicate detection stays ledger-based (no DB scans);
        # vectorized FK/id checks run through validate_arrow_batch.
        duplicate_ids = [id for id, found in ledger.fk_lookup(table_name, set(ids)).items() if found]
        if duplicate_ids and not add_mode:
            raise JobStateError(
                f"Duplicate ids across flushes in table '{table_name}': {sorted(duplicate_ids)[:5]} ..."
            )
        validate_arrow_batch(
            table_name,
            arrow_table,
            {},
            dataset,
            raise_or_warn="raise",
            fk_lookup=ledger.fk_lookup,
        )

        if add_mode:
            dataset.merge_records({table_name: arrow_table}, check_integrity="none")
        else:
            table = dataset.open_table(table_name)
            table.add(dataset._with_timestamp_columns(table, arrow_table))
        ledger.add(table_name, ids)
        table_counts[table_name] = table_counts.get(table_name, 0) + arrow_table.num_rows

    # ------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------

    def _finalize(
        self,
        dataset: Dataset,
        spec: ImportSpec,
        plan: ImportPlan,
        importer: DatasetImporter,
        job_id: str,
        table_counts: dict[str, int],
        census: "_MediaCensus",
        sinks: Sequence[ProgressSink],
        add_mode: bool,
    ) -> None:
        dataset.create_scalar_indexes()
        for table_name in dataset.info.tables:
            try:
                dataset.open_table(table_name).optimize()
            except Exception as exc:
                logger.warning("optimize() failed on table '%s': %s", table_name, exc)

        storage_mode = census.storage_mode(existing=dataset.info.storage_mode if add_mode else None)
        if storage_mode is not None:
            dataset.info.storage_mode = storage_mode
            dataset.info.to_json(dataset._info_file)

        provenance_file = dataset.path / "imports" / f"{job_id}.json"
        provenance_file.parent.mkdir(parents=True, exist_ok=True)
        provenance_file.write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "format": plan.format,
                    "importer_version": importer.importer_version,
                    "spec_fingerprint": spec.fingerprint(),
                    "plan_fingerprint": plan.plan_fingerprint,
                    "id_namespace": spec.ids.namespace or "",
                    "table_counts": table_counts,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        total = plan.totals.records
        done = table_counts.get(SchemaGroup.RECORD.value, 0)
        for sink in sinks:
            sink.emit(
                ProgressEvent(phase="finalize", done=done, total=total, table_counts=dict(table_counts), final=True)
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit_progress(self, sinks: Sequence[ProgressSink], plan: ImportPlan, table_counts: dict[str, int]) -> None:
        done = table_counts.get(SchemaGroup.RECORD.value, 0)
        for sink in sinks:
            sink.emit(
                ProgressEvent(phase="ingest", done=done, total=plan.totals.records, table_counts=dict(table_counts))
            )

    def _check_cancelled(self) -> None:
        if self.cancel_check is not None and self.cancel_check():
            raise JobStateError("Import cancelled.")

    def _assert_same_filesystem(self, staging_parent: Path, library_dir: Path) -> None:
        if staging_parent.stat().st_dev != library_dir.stat().st_dev:
            raise UnsupportedStorageError(
                "The staging area (<data_dir>/.pixano) and library/ must be on the same filesystem "
                "for atomic dataset promotion."
            )


def ledger_spilled(ledger: IdLedger) -> bool:
    """Whether the ledger has spilled to SQLite (its in-memory snapshot is gone)."""
    return ledger._connection is not None


def _approx_row_bytes(row: LanceModel) -> int:
    size = 64  # rough per-row overhead
    for attribute in ("raw_bytes", "blob", "preview", "content"):
        value = getattr(row, attribute, None)
        if isinstance(value, (bytes, str)):
            size += len(value)
    return size


def _stamp_image_previews(dataset: Dataset, table_name: str, rows: list[LanceModel]) -> None:
    """Stamp 64x64 PNG grid thumbnails on embedded image rows (spec finalize step).

    Runs at flush time so every importer inherits it. A corrupt image skips its
    thumbnail — the grid shows no preview, the import never fails. Video posters
    are the P3.5 ffmpeg work; the Arrow flush path (first used by LeRobot) is
    covered there too.
    """
    schema = dataset.info.tables.get(table_name)
    if schema is None or not (is_image(schema) or is_sequence_frame(schema)):
        return
    for row in rows:
        raw_bytes = getattr(row, "raw_bytes", b"")
        if not raw_bytes or row.preview:
            continue
        try:
            with PIL.Image.open(io.BytesIO(raw_bytes)) as pil_image:
                row.preview = _generate_preview(pil_image)
            row.preview_format = "png"
        except Exception:  # noqa: BLE001 - a bad image must never fail the import
            continue


class _MediaCensus:
    """Tracks whether view rows carry embedded bytes, URIs, or both (spec §6)."""

    def __init__(self) -> None:
        self.saw_embedded = False
        self.saw_uri = False

    def observe_rows(self, dataset: Dataset, table_name: str, rows: list[LanceModel]) -> None:
        if not self._is_view_table(dataset, table_name):
            return
        for row in rows:
            if getattr(row, "raw_bytes", b""):
                self.saw_embedded = True
            if getattr(row, "uri", ""):
                self.saw_uri = True

    def observe_arrow(self, dataset: Dataset, table_name: str, arrow_table: pa.Table) -> None:
        if not self._is_view_table(dataset, table_name):
            return
        names = set(arrow_table.schema.names)
        if "raw_bytes" in names:
            lengths = pc.binary_length(arrow_table.column("raw_bytes").combine_chunks())
            if pc.any(pc.greater(lengths, 0)).as_py():
                self.saw_embedded = True
        if "uri" in names:
            lengths = pc.utf8_length(arrow_table.column("uri").combine_chunks())
            if pc.any(pc.greater(lengths, 0)).as_py():
                self.saw_uri = True

    def storage_mode(
        self, existing: 'Literal["filesystem", "embedded", "mixed"] | None' = None
    ) -> 'Literal["filesystem", "embedded", "mixed"] | None':
        if not self.saw_embedded and not self.saw_uri:
            return None  # no view media observed: leave the stored mode untouched
        observed: Literal["filesystem", "embedded", "mixed"] = (
            "mixed" if (self.saw_embedded and self.saw_uri) else ("embedded" if self.saw_embedded else "filesystem")
        )
        if existing is None:
            return observed
        return observed if existing == observed else "mixed"

    @staticmethod
    def _is_view_table(dataset: Dataset, table_name: str) -> bool:
        schema_cls = dataset.info.tables.get(table_name)
        if schema_cls is None:
            return False
        try:
            return schema_to_group(schema_cls) == SchemaGroup.VIEW and is_view(schema_cls)
        except ValueError:
            return False
