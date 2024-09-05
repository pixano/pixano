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
from tests.fixtures.datasets.builders.builder import DumbDatasetBuilder


class TestDatasetBuilder:
    @pytest.mark.parametrize(
        "source_dir, target_dir",
        [
            (tempfile.gettempdir(), tempfile.gettempdir()),
            (tempfile.gettempdir(), Path(tempfile.gettempdir())),
        ],
    )
    def test_init(self, dataset_item_image_bboxes_keypoint, info, source_dir, target_dir):
        builder = DumbDatasetBuilder(5, source_dir, target_dir, dataset_item_image_bboxes_keypoint, info)
        assert builder.source_dir == Path(source_dir)
        assert builder.target_dir == Path(target_dir)
        assert builder.previews_path == Path(target_dir) / Dataset._PREVIEWS_PATH
        assert builder.info == info
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

    @pytest.mark.parametrize("mode", ["create", "overwrite", "add"])
    @pytest.mark.parametrize("flush_every_n_samples", [None, 3])
    @pytest.mark.parametrize("compact_every_n_transactions", [None, 2])
    def test_build(self, dumb_builder, mode, flush_every_n_samples, compact_every_n_transactions):
        # Mock the compact method to register the call count
        compact_dataset_mock = MagicMock()
        compact_table_mock = MagicMock()
        dumb_builder.compact_dataset = compact_dataset_mock
        dumb_builder.compact_table = compact_table_mock

        dataset = dumb_builder.build(
            flush_every_n_samples=flush_every_n_samples,
            compact_every_n_transactions=compact_every_n_transactions,
            mode="create",
        )
        assert dumb_builder.info.name == "test"
        assert dumb_builder.info.description == "test"
        assert dumb_builder.info.num_elements == 5

        assert (dumb_builder.target_dir / Dataset._INFO_FILE).exists()
        assert (dumb_builder.target_dir / Dataset._DB_PATH).exists()
        assert (dumb_builder.target_dir / Dataset._FEATURES_VALUES_FILE).exists()
        assert (dumb_builder.target_dir / Dataset._SCHEMA_FILE).exists()

        assert isinstance(dataset, Dataset)
        assert dataset.info == dumb_builder.info
        assert dataset.num_rows == 5
        assert set(dataset.open_tables().keys()) == {"image", "item", "entities", "bboxes", "keypoint"}

        assert compact_dataset_mock.call_count == 1
        if compact_every_n_transactions is None:
            assert compact_table_mock.call_count == 0
        else:
            if flush_every_n_samples is None:
                assert compact_table_mock.call_count == 8
            elif flush_every_n_samples == 3:
                assert compact_table_mock.call_count == 0
            else:
                raise ValueError("Invalid flush_every_n_samples value, update test")

        if mode == "create":
            with pytest.raises(OSError, match="Dataset already exists"):
                dumb_builder.build(
                    flush_every_n_samples=flush_every_n_samples,
                    compact_every_n_transactions=compact_every_n_transactions,
                    mode=mode,
                )
            return

        # Mock the add method to register the call count
        # Not done before as the tables are created only when the build method is called the first time
        def _side_effect_table_add(self, *args, **kwargs):
            return self.add(*args, **kwargs)

        table_mocks = []
        for table in dumb_builder.open_tables().values():
            table_mock = MagicMock(side_effect=_side_effect_table_add)
            table.add = table_mock
            table_mocks.append(table_mock)

        dumb_builder.num_rows = 6
        dataset = dumb_builder.build(
            flush_every_n_samples=flush_every_n_samples,
            compact_every_n_transactions=compact_every_n_transactions,
            mode=mode,
        )

        assert dataset.num_rows == 6 if mode == "overwrite" else 11
        assert compact_dataset_mock.call_count == 2

        if compact_every_n_transactions is None:
            assert compact_table_mock.call_count == 0
        else:
            if flush_every_n_samples is None:
                assert compact_table_mock.call_count == 18
            elif flush_every_n_samples == 3:
                assert compact_table_mock.call_count == 2
            else:
                raise ValueError("Invalid flush_every_n_samples value, update test")

        for mock in table_mocks:
            mock.call_count == 2 if flush_every_n_samples is None else 1

    def test_build_error(self):
        class WrongIdBuilder(DatasetBuilder):
            def generate_data(self):
                yield {
                    self.item_schema_name: self.item_schema(id="id with spaces", metadata="metadata", split="train")
                }

        class WrongSchemaNameBuilder(DatasetBuilder):
            def generate_data(self):
                yield {"wrong_schema": self.item_schema(id="id", metadata="metadata", split="train")}

        with pytest.raises(ValueError, match="ids should not contain spaces"):
            WrongIdBuilder(
                tempfile.mkdtemp(), tempfile.mkdtemp(), DatasetItem, DatasetInfo(name="test", description="test")
            ).build()

        with pytest.raises(AssertionError, match="Table wrong_schema not found in tables"):
            WrongSchemaNameBuilder(
                tempfile.mkdtemp(), tempfile.mkdtemp(), DatasetItem, DatasetInfo(name="test", description="test")
            ).build()
