# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import lancedb
import pytest

from pixano.datasets.builders.dataset_builder import DatasetBuilder
from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetItem, DatasetSchema
from pixano.datasets.workspaces import WorkspaceType
from pixano.features.schemas.source import Source, SourceKind
from tests.fixtures.datasets.builders.builder import DatasetBuilderImageBboxesKeypoint, DatasetBuilderVQA


class TestDatasetBuilder:
    @pytest.mark.parametrize(
        "target_dir",
        [
            (tempfile.gettempdir()),
            (Path(tempfile.gettempdir())),
        ],
    )
    def test_init(
        self,
        dataset_item_image_bboxes_keypoint,
        info_dataset_image_bboxes_keypoint,
        target_dir,
    ):
        builder = DatasetBuilderImageBboxesKeypoint(
            5, target_dir, dataset_item_image_bboxes_keypoint, info_dataset_image_bboxes_keypoint
        )
        assert builder.target_dir == Path(target_dir)
        assert builder.previews_path == Path(target_dir) / Dataset._PREVIEWS_PATH
        assert builder.info == info_dataset_image_bboxes_keypoint
        assert isinstance(builder.dataset_schema, DatasetSchema)
        assert set(builder.dataset_schema.schemas.keys()) == {"image", "item", "entities", "bboxes", "keypoint"}
        for (key1, value1), (key2, value2) in zip(
            builder.schemas.items(),
            dataset_item_image_bboxes_keypoint.to_dataset_schema().schemas.items(),
            strict=True,
        ):
            assert key1 == key2
            assert type(value1) is type(value2)
        assert isinstance(builder.db, lancedb.DBConnection)
        assert builder.db._uri == str(Path(target_dir) / Dataset._DB_PATH)

    @pytest.mark.parametrize(
        "target_dir",
        [
            (tempfile.gettempdir()),
            (Path(tempfile.gettempdir())),
        ],
    )
    def test_init_vqa(
        self,
        dataset_item_vqa,
        info_dataset_vqa,
        target_dir,
    ):
        builder = DatasetBuilderVQA(4, target_dir, dataset_item_vqa, info_dataset_vqa)
        assert builder.target_dir == Path(target_dir)
        assert builder.previews_path == Path(target_dir) / Dataset._PREVIEWS_PATH
        assert builder.info == info_dataset_vqa
        assert isinstance(builder.dataset_schema, DatasetSchema)
        assert set(builder.dataset_schema.schemas.keys()) == {"image", "item", "conversations", "messages"}
        for (key1, value1), (key2, value2) in zip(
            builder.schemas.items(),
            dataset_item_vqa.to_dataset_schema().schemas.items(),
            strict=True,
        ):
            assert key1 == key2
            assert type(value1) is type(value2)
        assert isinstance(builder.db, lancedb.DBConnection)
        assert builder.db._uri == str(Path(target_dir) / Dataset._DB_PATH)

    def test_add_source(self, dataset_builder_image_bboxes_keypoint: DatasetBuilderImageBboxesKeypoint):
        source_table = dataset_builder_image_bboxes_keypoint.db.create_table("source", schema=Source, mode="create")

        id = dataset_builder_image_bboxes_keypoint.add_source("source", "model", {"model_id": "model_0"})
        assert len(id) == 22
        id = dataset_builder_image_bboxes_keypoint.add_source("source_2", SourceKind.OTHER, {}, "my_id")
        assert id == "my_id"

        assert source_table.count_rows() == 2

    def test_add_ground_truth_source(self, dataset_builder_image_bboxes_keypoint: DatasetBuilderImageBboxesKeypoint):
        source_table = dataset_builder_image_bboxes_keypoint.db.create_table("source", schema=Source, mode="create")
        id = dataset_builder_image_bboxes_keypoint.add_ground_truth_source({"model_id": "model_0"})
        assert id == "ground_truth"
        assert source_table.count_rows() == 1

    @pytest.mark.parametrize("mode", ["create", "overwrite", "add"])
    @pytest.mark.parametrize("flush_every_n_samples", [None, 3])
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
        # Mock the compact method to register the call count
        compact_dataset_mock = MagicMock()
        compact_table_mock = MagicMock()
        dataset_builder_image_bboxes_keypoint.compact_dataset = compact_dataset_mock
        dataset_builder_image_bboxes_keypoint.compact_table = compact_table_mock

        dataset = dataset_builder_image_bboxes_keypoint.build(
            flush_every_n_samples=flush_every_n_samples,
            compact_every_n_transactions=compact_every_n_transactions,
            mode="create",
            check_integrity=check_integrity,
        )
        assert dataset_builder_image_bboxes_keypoint.info.description == "Description dataset_image_bboxes_keypoint."
        assert dataset_builder_image_bboxes_keypoint.info.workspace == WorkspaceType.IMAGE

        assert (dataset_builder_image_bboxes_keypoint.target_dir / Dataset._INFO_FILE).exists()
        assert (dataset_builder_image_bboxes_keypoint.target_dir / Dataset._DB_PATH).exists()
        assert (dataset_builder_image_bboxes_keypoint.target_dir / Dataset._FEATURES_VALUES_FILE).exists()
        assert (dataset_builder_image_bboxes_keypoint.target_dir / Dataset._SCHEMA_FILE).exists()

        assert isinstance(dataset, Dataset)
        assert dataset.info == dataset_builder_image_bboxes_keypoint.info
        assert dataset.num_rows == 5
        assert set(dataset.open_tables().keys()) == {"image", "item", "entities", "bboxes", "keypoint"}

        assert compact_dataset_mock.call_count == 1
        if compact_every_n_transactions is None:
            assert compact_table_mock.call_count == 0
        else:
            if flush_every_n_samples is None:
                assert compact_table_mock.call_count == 6
            elif flush_every_n_samples == 3:
                assert compact_table_mock.call_count == 0
            else:
                raise ValueError("Invalid flush_every_n_samples value, update test")

        if mode == "create":
            with pytest.raises(OSError, match="Dataset already exists"):
                dataset_builder_image_bboxes_keypoint.build(
                    flush_every_n_samples=flush_every_n_samples,
                    compact_every_n_transactions=compact_every_n_transactions,
                    mode=mode,
                    check_integrity=check_integrity,
                )
            return

        # Mock the add method to register the call count
        # Not done before as the tables are created only when the build method is called the first time
        def _side_effect_table_add(self, *args, **kwargs):
            return self.add(*args, **kwargs)

        table_mocks = []
        for table in dataset_builder_image_bboxes_keypoint.open_tables().values():
            table_mock = MagicMock(side_effect=_side_effect_table_add)
            table.add = table_mock
            table_mocks.append(table_mock)

        dataset_builder_image_bboxes_keypoint.num_rows = 6
        dataset = dataset_builder_image_bboxes_keypoint.build(
            flush_every_n_samples=flush_every_n_samples,
            compact_every_n_transactions=compact_every_n_transactions,
            mode=mode,
            check_integrity="none",
        )

        assert dataset.num_rows == 6 if mode == "overwrite" else 11
        assert compact_dataset_mock.call_count == 2

        if compact_every_n_transactions is None:
            assert compact_table_mock.call_count == 0
        else:
            if flush_every_n_samples is None:
                assert compact_table_mock.call_count == 14
            elif flush_every_n_samples == 3:
                assert compact_table_mock.call_count == 2
            else:
                raise ValueError("Invalid flush_every_n_samples value, update test")

        for mock in table_mocks:
            mock.call_count == 2 if flush_every_n_samples is None else 1

    @pytest.mark.parametrize("mode", ["create", "overwrite", "add"])
    @pytest.mark.parametrize("flush_every_n_samples", [None, 3])
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
        # Mock the compact method to register the call count
        compact_dataset_mock = MagicMock()
        compact_table_mock = MagicMock()
        dataset_builder_vqa.compact_dataset = compact_dataset_mock
        dataset_builder_vqa.compact_table = compact_table_mock

        dataset = dataset_builder_vqa.build(
            flush_every_n_samples=flush_every_n_samples,
            compact_every_n_transactions=compact_every_n_transactions,
            mode="create",
            check_integrity=check_integrity,
        )
        assert dataset_builder_vqa.info.description == "Description dataset_vqa."
        assert dataset_builder_vqa.info.workspace == WorkspaceType.IMAGE_VQA

        assert (dataset_builder_vqa.target_dir / Dataset._INFO_FILE).exists()
        assert (dataset_builder_vqa.target_dir / Dataset._DB_PATH).exists()
        assert (dataset_builder_vqa.target_dir / Dataset._FEATURES_VALUES_FILE).exists()
        assert (dataset_builder_vqa.target_dir / Dataset._SCHEMA_FILE).exists()

        assert isinstance(dataset, Dataset)
        assert dataset.info == dataset_builder_vqa.info
        assert dataset.num_rows == 4
        assert set(dataset.open_tables().keys()) == {"image", "item", "conversations", "messages"}

        assert compact_dataset_mock.call_count == 1
        if compact_every_n_transactions is None:
            assert compact_table_mock.call_count == 0
        else:
            if flush_every_n_samples is None:
                assert compact_table_mock.call_count == 8
            elif flush_every_n_samples == 3:
                assert compact_table_mock.call_count == 1
            else:
                raise ValueError("Invalid flush_every_n_samples value, update test")

        if mode == "create":
            with pytest.raises(OSError, match="Dataset already exists"):
                dataset_builder_vqa.build(
                    flush_every_n_samples=flush_every_n_samples,
                    compact_every_n_transactions=compact_every_n_transactions,
                    mode=mode,
                    check_integrity=check_integrity,
                )
            return

        # Mock the add method to register the call count
        # Not done before as the tables are created only when the build method is called the first time
        def _side_effect_table_add(self, *args, **kwargs):
            return self.add(*args, **kwargs)

        table_mocks = []
        for table in dataset_builder_vqa.open_tables().values():
            table_mock = MagicMock(side_effect=_side_effect_table_add)
            table.add = table_mock
            table_mocks.append(table_mock)

        dataset_builder_vqa.num_rows = 5
        dataset = dataset_builder_vqa.build(
            flush_every_n_samples=flush_every_n_samples,
            compact_every_n_transactions=compact_every_n_transactions,
            mode=mode,
            check_integrity="none",
        )

        assert dataset.num_rows == 5 if mode == "overwrite" else 9
        assert compact_dataset_mock.call_count == 2

        if compact_every_n_transactions is None:
            assert compact_table_mock.call_count == 0
        else:
            if flush_every_n_samples is None:
                assert compact_table_mock.call_count == 16
            elif flush_every_n_samples == 3:
                assert compact_table_mock.call_count == 3
            else:
                raise ValueError("Invalid flush_every_n_samples value, update test")

        for mock in table_mocks:
            mock.call_count == 2 if flush_every_n_samples is None else 1

    def test_build_error(self, dataset_builder_image_bboxes_keypoint):
        class WrongIdBuilder(DatasetBuilder):
            def generate_data(self):
                yield {
                    self.item_schema_name: self.item_schema(id="id with spaces", metadata="metadata", split="train")
                }

        class WrongSchemaNameBuilder(DatasetBuilder):
            def generate_data(self):
                yield {"wrong_schema": self.item_schema(id="id", metadata="metadata", split="train")}

        with pytest.raises(KeyError, match="Table wrong_schema not found in tables"):
            WrongSchemaNameBuilder(
                tempfile.mkdtemp(), DatasetItem, DatasetInfo(name="test", description="test")
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
