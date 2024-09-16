# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from lancedb.db import LanceTable
from lancedb.query import LanceQueryBuilder

from pixano.datasets.dataset import Dataset
from pixano.datasets.queries import TableQueryBuilder
from pixano.features.schemas.views.image import Image


@pytest.fixture(scope="class")
def image_table(dataset_multi_view_tracking_and_image: Dataset) -> LanceTable:
    return dataset_multi_view_tracking_and_image.open_table("image")


class TestTableQueryBuilder:
    def test_init(self, image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        assert builder.table == image_table
        assert builder._columns is None
        assert builder._where is None
        assert builder._prefilter is False
        assert builder._limit is None
        assert builder._offset is None
        assert builder._order_by == []
        assert builder._descending == []
        assert builder._function_called == {
            "select": False,
            "where": False,
            "limit": False,
            "offset": False,
            "order_by": False,
            "build": False,
        }

        with pytest.raises(ValueError, match="table must be a LanceTable."):
            TableQueryBuilder(123)

    def test_select(self, image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        builder.select(["column1", "column2"])
        assert builder._columns == ["id", "column1", "column2"]
        assert builder._function_called["select"] is True

        with pytest.raises(ValueError, match=r"select\(\) can only be called once."):
            builder.select(["column1", "column2"])

        with pytest.raises(ValueError, match="columns must be a list or a dictionary."):
            builder = TableQueryBuilder(image_table)
            builder.select("not_a_list")

        with pytest.raises(ValueError, match="columns must be a dictionary with string keys and values."):
            builder = TableQueryBuilder(image_table)
            builder.select({"key": 1, "key2": 2})

        with pytest.raises(ValueError, match="columns must be a list of strings."):
            builder = TableQueryBuilder(image_table)
            builder.select([1, 2, 3])

    def test_where(self, image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        builder.where("column1 = 'value'", True)
        assert builder._where == "column1 = 'value'"
        assert builder._prefilter is True
        assert builder._function_called["where"] is True

        with pytest.raises(ValueError, match=r"where\(\) can only be called once."):
            builder.where(123)

        with pytest.raises(ValueError, match="where must be a string."):
            builder = TableQueryBuilder(image_table)
            builder.where(123)

        with pytest.raises(ValueError, match="prefilter must be a boolean."):
            builder = TableQueryBuilder(image_table)
            builder.where("column1 = 'value'", "not_a_boolean")

    def test_limit(self, image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        builder.limit(10)
        assert builder._limit == 10
        assert builder._function_called["limit"] is True

        with pytest.raises(ValueError, match=r"limit\(\) can only be called once."):
            builder.limit(5)

        with pytest.raises(ValueError, match="limit must be None or a positive integer."):
            builder = TableQueryBuilder(image_table)
            builder.limit(-1)

    def test_offset(self, image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        builder.offset(5)
        assert builder._offset == 5
        assert builder._function_called["offset"] is True

        with pytest.raises(ValueError, match=r"offset\(\) can only be called once."):
            builder.offset(5)

        with pytest.raises(ValueError, match="offset must be None or a positive integer."):
            builder = TableQueryBuilder(image_table)
            builder.offset(-1)

    def test_order_by(self, image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        builder.order_by("column1")
        assert builder._order_by == ["column1"]
        assert builder._descending == [False]

        builder = TableQueryBuilder(image_table)
        builder.order_by(["column1", "column2"], True)
        assert builder._order_by == ["column1", "column2"]
        assert builder._descending == [True, True]

        builder = TableQueryBuilder(image_table)
        builder.order_by(["column1", "column2"], descending=[True, False])
        assert builder._order_by == ["column1", "column2"]
        assert builder._descending == [True, False]

        with pytest.raises(ValueError, match=r"order_by\(\) can only be called once."):
            builder.order_by("column1")

        with pytest.raises(ValueError, match="order_by must be a string or a list of strings."):
            builder = TableQueryBuilder(image_table)
            builder.order_by(123)

        with pytest.raises(
            ValueError, match="descending must be a boolean or a list of booleans with the same length as order_by."
        ):
            builder = TableQueryBuilder(image_table)
            builder.order_by(["column1", "column2"], descending=[True])

        with pytest.raises(
            ValueError, match="descending must be a boolean or a list of booleans with the same length as order_by."
        ):
            builder = TableQueryBuilder(image_table)
            builder.order_by(["column1", "column2"], descending=1)

        with pytest.raises(
            ValueError, match="descending must be a boolean or a list of booleans with the same length as order_by."
        ):
            builder = TableQueryBuilder(image_table)
            builder.order_by(["column1", "column2"], descending=[True, 1])

        with pytest.raises(ValueError):
            builder.order_by(123)

    def test_build_no_order_and_no_offset(self, image_table: LanceTable):
        # Test with select
        builder = TableQueryBuilder(image_table)
        query = builder.select(["url"]).build(False)
        assert isinstance(query, LanceQueryBuilder)
        assert builder._function_called["build"] is True

        rows = query.to_list()
        for row in rows:
            assert set(row.keys()) == {"id", "url"}
        assert len(rows) == 4

        # Test with limit
        builder = TableQueryBuilder(image_table)
        query = builder.limit(2).build(False)

        rows = query.to_list()
        assert len(rows) == 2
        for row in rows:
            assert set(row.keys()) == {"id", "item_ref", "parent_ref", "url", "width", "format", "height"}

        # Test with where
        builder = TableQueryBuilder(image_table)
        query = builder.where("url = 'image_1.jpg'").build(False)

        rows = query.to_list()
        assert len(rows) == 1
        for row in rows:
            assert row["id"] == "image_1"
            assert row["url"] == "image_1.jpg"

        # Test without order or offset and get_order=True
        builder = TableQueryBuilder(image_table)
        query, order = builder.where("url = 'image_1.jpg'").build(True)
        assert order is None
        rows = query.to_list()
        assert len(rows) == 1
        for row in rows:
            assert row["id"] == "image_1"
            assert row["url"] == "image_1.jpg"

        # Test cannot call build twice
        with pytest.raises(ValueError, match=r"build\(\) can only be called once."):
            builder.build()

        with pytest.raises(
            ValueError,
            match=r"At least one of select\(\), where\(\), limit\(\), offset\(\), or order_by\(\) " r"must be called.",
        ):
            builder = TableQueryBuilder(image_table)
            builder.build()

    def test_build_with_order_without_offset(self, image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        query, order = builder.order_by("url", descending=True).build(True)
        assert order == ["image_4", "image_2", "image_1", "image_0"]

        builder = TableQueryBuilder(image_table)
        query, order = builder.order_by("url").build(True)
        assert order == ["image_0", "image_1", "image_2", "image_4"]

        builder = TableQueryBuilder(image_table)
        query, order = builder.order_by(["url", "width"], descending=[True, False]).build(True)
        assert order == ["image_4", "image_2", "image_1", "image_0"]

    def test_build_with_offset(self, image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        query = builder.offset(2).build(False)
        rows = query.to_list()
        assert len(rows) == 2
        assert rows[0]["id"] == "image_2"
        assert rows[1]["id"] == "image_4"

    def test_build_with_order_and_offset(self, image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        query, order = builder.order_by("url", descending=True).offset(1).build(True)
        assert order == ["image_2", "image_1", "image_0"]

    def test_to_pandas(self, image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        rows = builder.order_by("item_ref.id", descending=True).offset(1).to_pandas()
        for i, row in rows.iterrows():
            assert row["url"] == f"image_{2 - i}.jpg"
            assert row["id"] == f"image_{2 - i}"

    def test_to_pydantic(self, image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        rows = builder.order_by("item_ref.id", descending=True).offset(1).to_pydantic(Image)
        for i, row in enumerate(rows):
            assert row.url == f"image_{2 - i}.jpg"
            assert row.id == f"image_{2 - i}"

    def test_to_list(self, image_table):
        builder = TableQueryBuilder(image_table)
        rows = builder.order_by("url", descending=True).offset(1).to_list()
        assert len(rows) == 3
        for i, row in enumerate(rows):
            assert row["url"] == f"image_{2 - i}.jpg"
            assert row["id"] == f"image_{2 - i}"

    def test_to_polar(self, image_table):
        builder = TableQueryBuilder(image_table)
        df = builder.order_by("item_ref.id", descending=True).offset(1).to_polar()
        for i, row in enumerate(df.rows(named=True)):
            assert row["url"] == f"image_{2 - i}.jpg"
            assert row["id"] == f"image_{2 - i}"
