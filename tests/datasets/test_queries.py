# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from lancedb.db import LanceTable

from pixano.datasets import Dataset
from pixano.datasets.queries import TableQueryBuilder
from pixano.schemas.views.image import Image


@pytest.fixture(scope="class")
def image_table(dataset_image_bboxes_keypoint: Dataset) -> LanceTable:
    return dataset_image_bboxes_keypoint.open_table("images")


class TestTableQueryBuilder:
    def test_init(self, image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        assert builder.table == image_table
        assert builder._columns is None
        assert builder._where is None
        assert builder._limit is None
        assert builder._offset is None
        assert builder._order_by == []
        assert builder._descending == []

        with pytest.raises(ValueError, match="table must be a LanceTable."):
            TableQueryBuilder(123)

    def test_select_where_limit_and_offset_validation(self, image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        assert builder.select(["uri"])._columns == ["id", "uri"]

        with pytest.raises(ValueError, match=r"select\(\) can only be called once."):
            builder.select(["width"])

        with pytest.raises(ValueError, match="where must be a string."):
            TableQueryBuilder(image_table).where(123)

        with pytest.raises(ValueError, match="limit must be None or a positive integer."):
            TableQueryBuilder(image_table).limit(-1)

        with pytest.raises(ValueError, match="offset must be None or a positive integer."):
            TableQueryBuilder(image_table).offset(-1)

    def test_execute_with_select_and_where(self, image_table: LanceTable):
        rows = TableQueryBuilder(image_table).select(["uri"]).where("uri = 'image_1.jpg'").to_list()
        assert rows == [{"id": "image_1", "uri": "image_1.jpg"}]

    def test_execute_with_limit_and_offset(self, image_table: LanceTable):
        rows = TableQueryBuilder(image_table).order_by("uri").offset(1).limit(2).to_list()
        assert [row["id"] for row in rows] == ["image_1", "image_2"]

    def test_to_pandas_and_to_polars(self, image_table: LanceTable):
        pandas_rows = TableQueryBuilder(image_table).order_by("record_id", descending=True).offset(1).to_pandas()
        assert list(pandas_rows["id"]) == ["image_3", "image_2", "image_1", "image_0"]

        polars_rows = TableQueryBuilder(image_table).order_by("record_id", descending=True).offset(1).to_polars()
        assert polars_rows["id"].to_list() == ["image_3", "image_2", "image_1", "image_0"]

    def test_to_pydantic(self, image_table: LanceTable):
        rows = TableQueryBuilder(image_table).where("id in ('image_0', 'image_1')").to_pydantic(Image)
        assert [row.id for row in rows] == ["image_0", "image_1"]
        assert [row.logical_name for row in rows] == ["image", "image"]

    def test_build_requires_at_least_one_operation(self, image_table: LanceTable):
        with pytest.raises(
            ValueError,
            match=r"At least one of select\(\), where\(\), limit\(\), offset\(\), or order_by\(\) must be called.",
        ):
            TableQueryBuilder(image_table)._execute()
