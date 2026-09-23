# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Scale and memory-boundedness tests (spec §13-P3; plan P3.6).

All tests are marked `slow` — CI deselects them; run locally with
`uv run pytest tests/datasets/io/test_scale.py -m slow`. Memory ceilings are
deliberately generous (they catch O(dataset) blowups, not KB-level drift) and
measure ru_maxrss deltas, so a fat baseline process cannot mask a leak.
"""

import resource
import sys
import time
from pathlib import Path

import pytest

from pixano.datasets import Dataset
from pixano.datasets.io import ImportSpec, import_dataset
from pixano.datasets.io.reader import RecordBundleReader
from tests.datasets.io._toy_importer import ToyImporter


pytestmark = pytest.mark.slow


def _rss_bytes() -> int:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw if sys.platform == "darwin" else raw * 1024


def _spec(name: str) -> ImportSpec:
    return ImportSpec.model_validate({"dataset": {"name": name, "workspace": "image"}, "format": "auto"})


def _import_toy(tmp_path: Path, name: str, num_records: int, image_kb: int = 8) -> Dataset:
    importer = ToyImporter(num_records=num_records, batch_size=256, image_bytes=b"x" * (image_kb * 1024))
    result = import_dataset(tmp_path / "src", tmp_path / f"data_{name}", _spec(name), importer=importer)
    return Dataset(result.dataset_path)


class TestImportMemoryBounds:
    def test_import_rss_delta_is_bounded(self, tmp_path: Path):
        # 20k records x 8KB embedded media = ~160MB of payload streamed through
        # the engine; the process high-water mark must grow far less than the
        # payload (flush-bounded buffering), not proportionally to it.
        baseline = _rss_bytes()
        dataset = _import_toy(tmp_path, "scale_import", num_records=20_000)
        delta_mb = (_rss_bytes() - baseline) / (1024 * 1024)

        assert dataset.open_table("records").count_rows() == 20_000
        assert delta_mb < 600, f"import RSS grew by {delta_mb:.0f}MB for a 160MB payload"

    def test_import_time_is_roughly_linear(self, tmp_path: Path):
        def timed(name: str, count: int) -> float:
            start = time.monotonic()
            _import_toy(tmp_path, name, num_records=count, image_kb=1)
            return time.monotonic() - start

        small = timed("lin_small", 2_000)
        large = timed("lin_large", 20_000)
        # 10x the rows must cost well under 30x the time (superlinear blowups
        # like per-row table scans show up as 50-100x here).
        assert large < max(small, 0.5) * 30, f"2k: {small:.1f}s vs 20k: {large:.1f}s"


class TestExportMemoryBounds:
    def test_export_streams_blobs_under_byte_budget(self, tmp_path: Path):
        dataset = _import_toy(tmp_path, "scale_export", num_records=5_000, image_kb=16)

        from pixano.datasets.io.formats.pixano_jsonl.exporter import PixanoJsonlExporter

        baseline = _rss_bytes()
        reader = RecordBundleReader(page_size=512, max_bytes_in_flight=8 * 1024 * 1024)
        exported = PixanoJsonlExporter(media="files", reader=reader).export(dataset, tmp_path / "exported")
        delta_mb = (_rss_bytes() - baseline) / (1024 * 1024)

        assert any(exported.glob("*/metadata.jsonl"))
        # 5k x 16KB = 80MB of blobs; the reader pages them under an 8MB budget,
        # never holding them all.
        assert delta_mb < 400, f"export RSS grew by {delta_mb:.0f}MB for an 80MB blob payload"

    def test_reader_query_count_scales_with_pages_not_records(self, tmp_path: Path):
        dataset = _import_toy(tmp_path, "scale_reader", num_records=4_096, image_kb=1)
        queries: list[str] = []
        reader = RecordBundleReader(page_size=1_024, query_counter=queries.append)
        bundle_count = sum(1 for _ in reader.iter_bundles(dataset))

        assert bundle_count == 4_096
        pages = 4  # 4096 / 1024
        tables = len(dataset.info.tables)
        # ids scan + per-page record fetch + per-page per-table component fetches
        # (blob tables may sub-batch, hence the x4 headroom) — never per-record.
        assert len(queries) <= 1 + pages + pages * tables * 4, f"{len(queries)} queries for {bundle_count} records"
