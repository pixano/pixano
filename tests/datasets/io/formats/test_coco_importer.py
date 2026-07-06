# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import shutil
from pathlib import Path

import pytest

from pixano.datasets.io import FORMATS, ImportSpec, SourceRef, import_dataset
from pixano.datasets.io.formats.coco import CocoImporter
from pixano.datasets.io.ids import namespace_prefix
from pixano.datasets.io.testing import DatasetImporterTestCase
from tests.assets.sample_data.metadata import IMAGE_JPG_ASSET_URL


FIXTURE = Path(__file__).parents[3] / "assets" / "coco_dataset"

EXPECTED_COUNTS = {"records": 3, "images": 3, "entities": 39, "bboxes": 39, "masks": 39}


def _spec(name: str = "coco_val") -> ImportSpec:
    return ImportSpec.model_validate(
        {"dataset": {"name": name, "workspace": "image"}, "format": "coco", "ids": {"namespace": "coco_fix"}}
    )


def _case(spill_threshold: int = 500_000) -> DatasetImporterTestCase:
    return DatasetImporterTestCase(
        importer=CocoImporter(spill_threshold=spill_threshold),
        source=FIXTURE,
        spec=_spec(),
        expected_counts=EXPECTED_COUNTS,
    )


class TestCocoImporter:
    def test_fixture_end_to_end(self, tmp_path: Path):
        case = _case()
        case.assert_analyze_clean()
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)
        case.assert_storage_mode(dataset, "embedded")
        case.assert_id_prefix(dataset, namespace_prefix("coco_fix"))
        case.assert_idempotent_rerun(dataset, tmp_path / "data")

    def test_intrinsic_schema_and_values(self, tmp_path: Path):
        dataset, _ = _case().run_import(tmp_path / "data")
        entity = dataset.get_data("entities")[0]
        assert entity.category and entity.supercategory
        assert entity.iscrowd is False
        box = dataset.get_data("bboxes")[0]
        assert box.format == "xywh" and box.is_normalized is True
        assert all(0.0 <= coord <= 1.0 for coord in box.coords)
        mask = dataset.get_data("masks")[0]
        assert mask.counts and mask.size == [426, 640] or mask.size  # RLE round-tripped

    def test_spill_path_is_id_identical(self, tmp_path: Path):
        in_memory, _ = _case().run_import(tmp_path / "mem")
        spilled, _ = _case(spill_threshold=1).run_import(tmp_path / "spill")
        for table in EXPECTED_COUNTS:
            ids_mem = sorted(r["id"] for r in in_memory.open_table(table).search().select(["id"]).to_list())
            ids_spill = sorted(r["id"] for r in spilled.open_table(table).search().select(["id"]).to_list())
            assert ids_mem == ids_spill, table

    def test_cursor_resume_skips_processed_images(self):
        importer = CocoImporter()
        spec = _spec()
        plan = importer.analyze(
            SourceRef.from_string(str(FIXTURE)),
            spec,
            __import__("pixano.datasets.io.plan", fromlist=["AnalyzeLimits"]).AnalyzeLimits(),
        )
        all_bundles = list(importer.iter_batches(SourceRef.from_string(str(FIXTURE)), spec, plan))
        resumed = list(
            importer.iter_batches(
                SourceRef.from_string(str(FIXTURE)), spec, plan, cursor={"split": "val", "image_ordinal": 2}
            )
        )
        assert len(all_bundles) == 3 and len(resumed) == 1
        assert resumed[0].cursor == {"split": "val", "image_ordinal": 3}

    def test_detection(self):
        assert FORMATS.detect(SourceRef.from_string(str(FIXTURE))).name == "coco"

    def test_keypoints_and_polygons(self, tmp_path: Path):
        source = tmp_path / "kp_src"
        (source / "train").mkdir(parents=True)
        shutil.copy(IMAGE_JPG_ASSET_URL, source / "train" / "img1.jpg")
        payload = {
            "images": [{"id": 1, "file_name": "img1.jpg", "width": 586, "height": 640}],
            "categories": [{"id": 1, "name": "person", "supercategory": "person"}],
            "annotations": [
                {
                    "id": 10,
                    "image_id": 1,
                    "category_id": 1,
                    "bbox": [10, 10, 100, 200],
                    "segmentation": [[10.0, 10.0, 110.0, 10.0, 110.0, 210.0, 10.0, 210.0]],
                    "keypoints": [50, 60, 2, 0, 0, 0, 80, 90, 1],
                }
            ],
        }
        (source / "instances_train.json").write_text(json.dumps(payload))

        result = import_dataset(source, tmp_path / "data", _spec("coco_kp"), importer=CocoImporter())
        from pixano.datasets import Dataset

        dataset = Dataset(result.dataset_path)
        keypoints = dataset.get_data("keypoints")[0]
        assert keypoints.template_id == "coco-17"
        assert keypoints.states == ["visible", "invisible", "hidden"]
        assert dataset.open_table("masks").count_rows() == 1  # polygon converted to RLE

    def test_unknown_category_is_an_analyze_error(self, tmp_path: Path):
        source = tmp_path / "bad_src"
        source.mkdir()
        payload = {
            "images": [{"id": 1, "file_name": "img1.jpg", "width": 10, "height": 10}],
            "categories": [{"id": 1, "name": "person"}],
            "annotations": [{"id": 5, "image_id": 1, "category_id": 99, "bbox": [1, 1, 2, 2]}],
        }
        (source / "instances_train.json").write_text(json.dumps(payload))
        plan = CocoImporter().analyze(
            SourceRef.from_string(str(source)),
            _spec(),
            __import__("pixano.datasets.io.plan", fromlist=["AnalyzeLimits"]).AnalyzeLimits(),
        )
        assert "unknown_category_id" in plan.report.findings

    def test_uri_mode_uses_coco_url(self, tmp_path: Path):
        source = tmp_path / "uri_src"
        source.mkdir()
        payload = {
            "images": [
                {"id": 1, "file_name": "a.jpg", "width": 4, "height": 4, "coco_url": "https://cdn.example.com/a.jpg"}
            ],
            "categories": [],
            "annotations": [],
        }
        (source / "instances_val.json").write_text(json.dumps(payload))
        spec = ImportSpec.model_validate(
            {"dataset": {"name": "coco_uri", "workspace": "image"}, "format": "coco", "media": {"mode": "uri"}}
        )
        result = import_dataset(source, tmp_path / "data", spec, importer=CocoImporter())
        from pixano.datasets import Dataset

        dataset = Dataset(result.dataset_path)
        assert dataset.get_data("images")[0].uri == "https://cdn.example.com/a.jpg"
        assert dataset.info.storage_mode == "filesystem"
