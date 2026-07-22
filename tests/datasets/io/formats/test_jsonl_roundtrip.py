# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from pathlib import Path

import pytest

from pixano.datasets import Dataset
from pixano.datasets.io import ImportSpec, export_dataset, ffprobe_available, import_dataset
from pixano.datasets.io.formats.pixano_jsonl import PixanoJsonlImporter
from pixano.datasets.io.reader import RecordBundleReader
from tests.datasets.io.formats.test_jsonl_importer import EXPECTED_COUNTS, NEEDS_FFPROBE, SPECS, materialize_corpus


def _sorted_ids(dataset: Dataset) -> dict[str, list[str]]:
    return {
        name: sorted(row["id"] for row in dataset.open_table(name).search().select(["id"]).limit(None).to_list())
        for name in dataset.info.tables
    }


def _import(source: Path, data_dir: Path, name: str, spec_overrides: dict | None = None) -> Dataset:
    payload = {**SPECS[name], "ids": {"namespace": name}, **(spec_overrides or {})}
    spec = ImportSpec.model_validate(payload)
    result = import_dataset(source, data_dir, spec, importer=PixanoJsonlImporter())
    return Dataset(result.dataset_path)


ROUND_TRIP_CORPORA = sorted(SPECS)


class TestGoldenRoundTrips:
    @pytest.mark.parametrize("name", ROUND_TRIP_CORPORA)
    def test_import_export_reimport_is_id_equal(self, name: str, tmp_path: Path):
        if name in NEEDS_FFPROBE and not ffprobe_available():
            pytest.skip("ffprobe not installed")

        source = materialize_corpus(name, tmp_path / "src")
        first = _import(source, tmp_path / "data1", name)

        media = "uris" if first.info.storage_mode == "filesystem" else "files"
        exported = export_dataset(first, tmp_path / "exported", media=media)

        second = _import(exported, tmp_path / "data2", name)

        assert _sorted_ids(second) == _sorted_ids(first)  # the id-equal round-trip contract (spec §5)
        for table_name, expected in EXPECTED_COUNTS[name].items():
            assert second.open_table(table_name).count_rows() == expected

    def test_exported_yaml_is_a_valid_spec(self, tmp_path: Path):
        source = materialize_corpus("voc_like", tmp_path / "src")
        dataset = _import(source, tmp_path / "data", "voc_like")
        exported = export_dataset(dataset, tmp_path / "exported")

        spec = ImportSpec.from_yaml(exported / "dataset.yaml")
        assert spec.format == "pixano_jsonl"
        from pixano.datasets.io.spec import resolve_dataset_info

        recompiled = resolve_dataset_info(spec)
        assert set(recompiled.tables) == set(dataset.info.tables)
        assert "license" in recompiled.record.model_fields  # custom attrs survive the yaml

    def test_annotation_values_survive(self, tmp_path: Path):
        source = materialize_corpus("voc_like", tmp_path / "src")
        first = _import(source, tmp_path / "data1", "voc_like")
        exported = export_dataset(first, tmp_path / "exported")
        second = _import(exported, tmp_path / "data2", "voc_like")

        original = first.get_data("bboxes")[0]
        reimported = second.get_data("bboxes")[0]
        assert reimported.coords == original.coords
        assert reimported.format == original.format
        assert reimported.is_normalized == original.is_normalized
        assert second.get_data("masks")[0].counts == first.get_data("masks")[0].counts
        assert second.get_data("records")[0].license == "voc2007"

    def test_annotation_attrs_survive(self, tmp_path: Path):
        source = materialize_corpus("mel", tmp_path / "src")
        first = _import(source, tmp_path / "data1", "mel")
        exported = export_dataset(first, tmp_path / "exported")
        second = _import(exported, tmp_path / "data2", "mel")

        original_bbox = first.get_data("bboxes")[0]
        reimported_bbox = second.get_data("bboxes")[0]
        assert reimported_bbox.annotator == original_bbox.annotator == "alice"

        original_span = first.get_data("text_spans")[0]
        reimported_span = second.get_data("text_spans")[0]
        assert reimported_span.role == original_span.role == "title"

    def test_uris_mode_refuses_embedded_dataset(self, tmp_path: Path):
        from pixano.datasets.io import SpecValidationError

        source = materialize_corpus("voc_like", tmp_path / "src")
        dataset = _import(source, tmp_path / "data", "voc_like")
        with pytest.raises(SpecValidationError, match="files"):
            export_dataset(dataset, tmp_path / "exported", media="uris")

    def test_export_includes_record_base_fields(self, tmp_path: Path):
        source = materialize_corpus("mel", tmp_path / "src")
        first = _import(source, tmp_path / "data1", "mel")

        exported = export_dataset(
            first,
            tmp_path / "exported",
            media="files",
            options={"include_record_fields": ["status", "created_at"]},
        )

        # Check the exported JSONL contains status and created_at in attrs
        jsonl_path = exported / "train" / "metadata.jsonl"
        lines = jsonl_path.read_text().strip().split("\n")
        # First line is the header, second line is the record
        record_line = json.loads(lines[1])
        assert "attrs" in record_line
        assert record_line["attrs"]["status"] == "new"
        assert "created_at" in record_line["attrs"]

        # Re-import and verify the values survive the round-trip EXACTLY —
        # including timestamps (fresh imports must not restamp created_at).
        second = _import(exported, tmp_path / "data2", "mel")
        original = first.get_data("records")[0]
        rec = second.get_data("records")[0]
        assert rec.status == original.status
        assert rec.created_at == original.created_at

    def test_export_excludes_record_base_fields_by_default(self, tmp_path: Path):
        source = materialize_corpus("mel", tmp_path / "src")
        first = _import(source, tmp_path / "data1", "mel")

        exported = export_dataset(first, tmp_path / "exported", media="files")

        # Default export should NOT include status/created_at in attrs
        jsonl_path = exported / "train" / "metadata.jsonl"
        lines = jsonl_path.read_text().strip().split("\n")
        record_line = json.loads(lines[1])
        attrs = record_line.get("attrs", {})
        assert "status" not in attrs
        assert "created_at" not in attrs

    def test_exported_yaml_contains_export_options(self, tmp_path: Path):
        source = materialize_corpus("mel", tmp_path / "src")
        dataset = _import(source, tmp_path / "data", "mel")
        exported = export_dataset(
            dataset,
            tmp_path / "exported",
            options={"include_record_fields": ["status", "created_at"]},
        )
        yaml_content = (exported / "dataset.yaml").read_text()
        assert "include_record_fields" in yaml_content
        assert "status" in yaml_content
        assert "created_at" in yaml_content

        # The exported yaml must remain a VALID import spec (the option lives
        # under `options`, never as an unknown top-level key), and the export
        # must be fully re-importable as-is — the §5 round-trip contract.
        spec = ImportSpec.from_yaml(exported / "dataset.yaml")
        assert spec.options["include_record_fields"] == ["status", "created_at"]
        second = _import(exported, tmp_path / "data2", "mel")
        assert _sorted_ids(second) == _sorted_ids(dataset)

    def test_hand_authored_timestamps_are_preserved(self, tmp_path: Path):
        import shutil
        from datetime import datetime

        from tests.assets.sample_data.metadata import IMAGE_JPG_ASSET_URL

        split = tmp_path / "src" / "train"
        split.mkdir(parents=True)
        shutil.copy(IMAGE_JPG_ASSET_URL, split / "a.jpg")
        split.joinpath("metadata.jsonl").write_text(
            '{"id": "rec_1", "attrs": {"created_at": "2020-01-02T03:04:05", "status": "validated"}, '
            '"views": {"image": "a.jpg"}}\n',
            encoding="utf-8",
        )
        spec = ImportSpec.model_validate({"format": "pixano_jsonl", "dataset": {"name": "ts", "workspace": "image"}})
        result = import_dataset(tmp_path / "src", tmp_path / "data", spec, importer=PixanoJsonlImporter())
        rec = Dataset(result.dataset_path).get_data("records")[0]
        assert rec.created_at == datetime(2020, 1, 2, 3, 4, 5)
        assert rec.status == "validated"


class TestReaderGuarantees:
    def test_no_per_record_queries(self, tmp_path: Path):
        source = materialize_corpus("multiview", tmp_path / "src")
        dataset = _import(source, tmp_path / "data", "multiview")

        queries: list[str] = []
        reader = RecordBundleReader(page_size=8, query_counter=queries.append)
        bundles = list(reader.iter_bundles(dataset))

        assert len(bundles) == 1
        # 1 ids scan + 1 record page + at most a few sub-batches per component table —
        # bounded by tables, never by records.
        assert len(queries) <= 2 + 2 * len(dataset.info.tables)

    def test_bytes_in_flight_shrinks_blob_batches(self, tmp_path: Path):
        source = materialize_corpus("multiview", tmp_path / "src")
        dataset = _import(source, tmp_path / "data", "multiview")

        queries: list[str] = []
        # Budget below one image's size: image sub-batches must fall to size 1.
        reader = RecordBundleReader(max_bytes_in_flight=1_000, initial_blob_batch=64, query_counter=queries.append)
        bundles = list(reader.iter_bundles(dataset))
        assert bundles[0].components["images"] and len(bundles[0].components["images"]) == 2

    def test_completeness_on_fixture_dataset(self, dataset_multi_view_tracking_and_image: Dataset):
        reader = RecordBundleReader(page_size=3)
        bundles = list(reader.iter_bundles(dataset_multi_view_tracking_and_image))
        record_count = dataset_multi_view_tracking_and_image.open_table("records").count_rows()
        assert len(bundles) == record_count
        assert sorted({bundle.record_id for bundle in bundles}) == sorted(
            row["id"]
            for row in dataset_multi_view_tracking_and_image.open_table("records")
            .search()
            .select(["id"])
            .limit(None)
            .to_list()
        )
        total_components = sum(len(rows) for bundle in bundles for rows in bundle.components.values())
        expected_components = sum(
            dataset_multi_view_tracking_and_image.open_table(name).count_rows()
            for name in dataset_multi_view_tracking_and_image.info.tables
            if name not in ("records", "embeddings")
        )
        assert total_components >= expected_components - _embedding_rows(dataset_multi_view_tracking_and_image)


def _embedding_rows(dataset: Dataset) -> int:
    total = 0
    for name in dataset.info.tables:
        if "embedding" in name:
            total += dataset.open_table(name).count_rows()
    return total
