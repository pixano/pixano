# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pixano.datasets.builders.dataset_builder import DatasetBuilder
from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import Record
from tests.fixtures.datasets.builders.builder import DatasetBuilderImageBboxesKeypoint, DatasetBuilderVQA


class TestDatasetBuilder:
    def test_init_str(
        self,
        info_dataset_image_bboxes_keypoint,
    ):
        target_dir = str(Path(tempfile.mkdtemp()) / "dataset")
        builder = DatasetBuilderImageBboxesKeypoint(5, target_dir, info_dataset_image_bboxes_keypoint)
        assert builder.target_dir == Path(target_dir)
        assert builder.previews_path == Path(target_dir) / Dataset._PREVIEWS_PATH
        assert builder.info == info_dataset_image_bboxes_keypoint
        assert set(builder.schemas.keys()) == {"images", "records", "entities", "bboxes"}

    def test_init_path(
        self,
        info_dataset_image_bboxes_keypoint,
    ):
        target_dir = Path(tempfile.mkdtemp()) / "dataset"
        builder = DatasetBuilderImageBboxesKeypoint(5, target_dir, info_dataset_image_bboxes_keypoint)
        assert builder.target_dir == target_dir
        assert builder.previews_path == target_dir / Dataset._PREVIEWS_PATH
        assert builder.info == info_dataset_image_bboxes_keypoint
        assert set(builder.schemas.keys()) == {"images", "records", "entities", "bboxes"}

    def test_init_vqa_str(
        self,
        info_dataset_vqa,
    ):
        target_dir = str(Path(tempfile.mkdtemp()) / "dataset")
        builder = DatasetBuilderVQA(4, target_dir, info_dataset_vqa)
        assert builder.target_dir == Path(target_dir)
        assert builder.previews_path == Path(target_dir) / Dataset._PREVIEWS_PATH
        assert builder.info == info_dataset_vqa
        assert set(builder.schemas.keys()) == {"images", "records", "messages"}

    def test_init_vqa_path(
        self,
        info_dataset_vqa,
    ):
        target_dir = Path(tempfile.mkdtemp()) / "dataset"
        builder = DatasetBuilderVQA(4, target_dir, info_dataset_vqa)
        assert builder.target_dir == target_dir
        assert builder.previews_path == target_dir / Dataset._PREVIEWS_PATH
        assert builder.info == info_dataset_vqa
        assert set(builder.schemas.keys()) == {"images", "records", "messages"}

    @pytest.mark.parametrize("mode", ["create", "overwrite", "add"])
    @pytest.mark.parametrize("flush_every_n_samples", [1, 3])
    @pytest.mark.parametrize("compact_every_n_transactions", [None, 2])
    @pytest.mark.parametrize("check_integrity", ["raise", "warn", "none"])
    def test_build(
        self,
        dataset_builder_image_bboxes_keypoint,
        mode,
        flush_every_n_samples,
        compact_every_n_transactions,
        check_integrity,
    ):
        dataset = dataset_builder_image_bboxes_keypoint.build(
            flush_every_n_samples=flush_every_n_samples,
            compact_every_n_transactions=compact_every_n_transactions,
            mode="create",
            check_integrity=check_integrity,
        )
        assert dataset_builder_image_bboxes_keypoint.info.description == "Description dataset_image_bboxes_keypoint."
        assert dataset_builder_image_bboxes_keypoint.info.workspace == WorkspaceType.IMAGE

        assert (dataset_builder_image_bboxes_keypoint.target_dir / Dataset._INFO_FILE).exists()

        assert isinstance(dataset, Dataset)
        assert dataset.info.name == dataset_builder_image_bboxes_keypoint.info.name
        assert dataset.info.description == dataset_builder_image_bboxes_keypoint.info.description
        assert dataset.info.workspace == dataset_builder_image_bboxes_keypoint.info.workspace
        assert set(dataset.info.tables.keys()) == set(dataset_builder_image_bboxes_keypoint.info.tables.keys())
        assert dataset.num_rows == 5
        assert set(dataset.open_tables().keys()) == {"images", "records", "entities", "bboxes"}

        if mode == "create":
            with pytest.raises((OSError, ValueError), match="already exists"):
                dataset_builder_image_bboxes_keypoint.build(
                    flush_every_n_samples=flush_every_n_samples,
                    compact_every_n_transactions=compact_every_n_transactions,
                    mode=mode,
                    check_integrity=check_integrity,
                )
            return

        dataset_builder_image_bboxes_keypoint.num_rows = 6
        dataset = dataset_builder_image_bboxes_keypoint.build(
            flush_every_n_samples=flush_every_n_samples,
            compact_every_n_transactions=compact_every_n_transactions,
            mode=mode,
            check_integrity="none",
        )

        assert dataset.num_rows == 6 if mode == "overwrite" else 11

    @pytest.mark.parametrize("mode", ["create", "overwrite", "add"])
    @pytest.mark.parametrize("flush_every_n_samples", [1, 3])
    @pytest.mark.parametrize("compact_every_n_transactions", [None, 2])
    @pytest.mark.parametrize("check_integrity", ["raise", "warn", "none"])
    def test_build_vqa(
        self,
        dataset_builder_vqa,
        mode,
        flush_every_n_samples,
        compact_every_n_transactions,
        check_integrity,
    ):
        dataset = dataset_builder_vqa.build(
            flush_every_n_samples=flush_every_n_samples,
            compact_every_n_transactions=compact_every_n_transactions,
            mode="create",
            check_integrity=check_integrity,
        )
        assert dataset_builder_vqa.info.description == "Description dataset_vqa."
        assert dataset_builder_vqa.info.workspace == WorkspaceType.IMAGE_VQA

        assert (dataset_builder_vqa.target_dir / Dataset._INFO_FILE).exists()

        assert isinstance(dataset, Dataset)
        assert dataset.info.name == dataset_builder_vqa.info.name
        assert dataset.info.description == dataset_builder_vqa.info.description
        assert dataset.info.workspace == dataset_builder_vqa.info.workspace
        assert set(dataset.info.tables.keys()) == set(dataset_builder_vqa.info.tables.keys())
        assert dataset.num_rows == 4
        assert set(dataset.open_tables().keys()) == {"images", "records", "messages"}

        if mode == "create":
            with pytest.raises((OSError, ValueError), match="already exists"):
                dataset_builder_vqa.build(
                    flush_every_n_samples=flush_every_n_samples,
                    compact_every_n_transactions=compact_every_n_transactions,
                    mode=mode,
                    check_integrity=check_integrity,
                )
            return

        dataset_builder_vqa.num_rows = 5
        dataset = dataset_builder_vqa.build(
            flush_every_n_samples=flush_every_n_samples,
            compact_every_n_transactions=compact_every_n_transactions,
            mode=mode,
            check_integrity="none",
        )

        assert dataset.num_rows == 5 if mode == "overwrite" else 9

    def test_build_error(self, dataset_builder_image_bboxes_keypoint):
        class WrongIdBuilder(DatasetBuilder):
            def generate_data(self):
                yield {
                    self.record_table_name: self.record_schema(id="id with spaces", metadata="metadata", split="train")
                }

        class WrongSchemaNameBuilder(DatasetBuilder):
            def generate_data(self):
                yield {"wrong_schema": self.record_schema(id="id", metadata="metadata", split="train")}

        from tests.fixtures.datasets.dataset_info import RecordWithMetadata

        with pytest.raises(KeyError, match="Table wrong_schema not found in tables"):
            WrongSchemaNameBuilder(
                Path(tempfile.mkdtemp()) / "dataset",
                DatasetInfo(
                    name="test",
                    description="test",
                    record=RecordWithMetadata,
                ),
            ).build()

        with pytest.raises(ValueError, match="mode should be 'add', 'create' or 'overwrite' but got wrong_mode"):
            dataset_builder_image_bboxes_keypoint.build(mode="wrong_mode")

        with pytest.raises(
            ValueError, match="check_integrity should be 'raise', 'warn' or 'none' but got wrong_check_integrity"
        ):
            dataset_builder_image_bboxes_keypoint.build(check_integrity="wrong_check_integrity")

        with pytest.raises(ValueError, match="flush_every_n_samples should be greater than 0 but got -1"):
            dataset_builder_image_bboxes_keypoint.build(flush_every_n_samples=-1)

        with pytest.raises(ValueError, match="compact_every_n_transactions should be greater than 0 but got -1"):
            dataset_builder_image_bboxes_keypoint.build(compact_every_n_transactions=-1)
