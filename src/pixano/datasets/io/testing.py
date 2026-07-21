# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Reusable importer test harness (spec §7.4) — usable by third-party format authors.

TFDS-dummy-data style: run the real importer end to end into a temporary
data directory and assert per-table row counts, id namespacing, storage
mode, and add-mode idempotency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pixano.datasets.dataset import Dataset

from .api import import_dataset
from .engine import ImportResult
from .importer import DatasetImporter
from .plan import PreflightReport
from .spec import ImportSpec


@dataclass
class DatasetImporterTestCase:
    """End-to-end importer exercise: analyze → import → assertions."""

    importer: DatasetImporter
    source: Path | str
    spec: ImportSpec
    expected_counts: dict[str, int] = field(default_factory=dict)

    def run_import(self, data_dir: Path) -> tuple[Dataset, ImportResult]:
        """Import into `data_dir` and return the opened dataset + result."""
        result = import_dataset(self.source, data_dir, self.spec, importer=self.importer)
        return Dataset(result.dataset_path), result

    def assert_counts(self, dataset: Dataset) -> None:
        """Assert exact per-table row counts."""
        actual = {name: dataset.open_table(name).count_rows() for name in self.expected_counts}
        assert actual == self.expected_counts, f"table counts differ: {actual} != {self.expected_counts}"

    def assert_id_prefix(self, dataset: Dataset, ns8_prefix: str, table: str = "records") -> None:
        """Assert derived ids carry the namespace prefix (rollback contract, spec §8)."""
        ids = dataset.open_table(table).search().select(["id"]).limit(5).to_list()
        for row in ids:
            assert row["id"].startswith(f"{ns8_prefix}-"), f"id '{row['id']}' lacks prefix '{ns8_prefix}-'"

    def assert_storage_mode(self, dataset: Dataset, expected: str) -> None:
        """Assert the media census stamped the expected storage mode."""
        assert dataset.info.storage_mode == expected, f"{dataset.info.storage_mode} != {expected}"

    def assert_idempotent_rerun(self, dataset: Dataset, data_dir: Path) -> None:
        """Re-run the same import in add mode and assert no table grew."""
        counts_before = {name: dataset.open_table(name).count_rows() for name in dataset.info.tables}
        add_spec = self.spec.model_copy(update={"mode": "add"})
        import_dataset(self.source, data_dir, add_spec, importer=self.importer)
        counts_after = {name: dataset.open_table(name).count_rows() for name in dataset.info.tables}
        assert counts_after == counts_before, f"add-mode rerun changed counts: {counts_after} != {counts_before}"

    def assert_analyze_clean(self) -> PreflightReport:
        """Analyze the source and assert no error findings; returns the report."""
        from .api import analyze

        plan = analyze(self.source, self.spec, importer=self.importer)
        assert plan.report.is_valid, {code: f.suggestion for code, f in plan.report.findings.items()}
        return plan.report
