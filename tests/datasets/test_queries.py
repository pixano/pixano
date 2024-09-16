# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from unittest.mock import MagicMock

import pytest
from lancedb.db import LanceTable
from lancedb.query import LanceQueryBuilder

from pixano.datasets.dataset import Dataset
from pixano.datasets.queries import TableQueryBuilder
from pixano.datasets.utils import DatasetPaginationError


@pytest.fixture(scope="class")
def image_table(dataset_multi_view_tracking_and_image: Dataset) -> LanceTable:
    return dataset_multi_view_tracking_and_image.open_table("image")


class TestTableQueryBuilder:
    def test_init(image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        assert builder.table == image_table
        assert builder._columns is None
        assert builder._where is None
        assert builder._prefilter is False
        assert builder._limit is None
        assert builder._offset is None
        assert builder._order_by == []
        assert builder._descending is False
        assert builder._function_called == {
            "select": False,
            "where": False,
            "limit": False,
            "offset": False,
            "order_by": False,
            "build": False,
        }

    def test_select(image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        builder.select(["column1", "column2"])
        assert builder._columns == ["column1", "column2"]
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

    def test_where(image_table: LanceTable):
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

    def test_limit(image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        builder.limit(10)
        assert builder._limit == 10
        assert builder._function_called["limit"] is True

        with pytest.raises(ValueError, match=r"limit\(\) can only be called once."):
            builder.limit(5)

        with pytest.raises(ValueError, match="limit must be None or a positive integer."):
            builder = TableQueryBuilder(image_table)
            builder.limit(-1)

    def test_offset(image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        builder.offset(5)
        assert builder._offset == 5
        assert builder._function_called["offset"] is True

        with pytest.raises(ValueError, match=r"offset\(\) can only be called once."):
            builder.offset(5)

        with pytest.raises(ValueError, match="offset must be None or a positive integer."):
            builder = TableQueryBuilder(image_table)
            builder.offset(-1)

    def test_order_by(image_table: LanceTable):
        builder = TableQueryBuilder(image_table)
        builder.order_by("column1")
        assert builder._order_by == ["column1"]
        assert builder._descending is False

        builder.order_by(["column1", "column2"], descending=True)
        assert builder._order_by == ["column1", "column2"]
        assert builder._descending is True

        with pytest.raises(ValueError):
            builder.order_by(123)

    def test_build(image_table: LanceTable):
        mock_query_builder = MagicMock(spec=LanceQueryBuilder)
        image_table.search.return_value = mock_query_builder

        builder = TableQueryBuilder(image_table)
        builder.select(["column1"]).where("column1 = 'value'").limit(10).offset(5).order_by("column1")
        query = builder.build()

        assert query == mock_query_builder
        mock_query_builder.select.assert_called_with(["column1"])
        mock_query_builder.where.assert_called_with("column1 = 'value'", False)
        mock_query_builder.limit.assert_called_with(10)

        with pytest.raises(ValueError):
            builder.build()

    def test_build_with_order_by_and_offset(image_table: LanceTable):
        mock_query_builder = MagicMock(spec=LanceQueryBuilder)
        image_table.search.return_value = mock_query_builder
        image_table.search().select().where().limit().to_list.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]

        builder = TableQueryBuilder(image_table)
        builder.order_by("column1").offset(1).limit(1)
        query = builder.build()

        assert query == mock_query_builder
        mock_query_builder.where.assert_called_with("id in (2)", False)

    def test_build_no_results(image_table: LanceTable):
        mock_query_builder = MagicMock(spec=LanceQueryBuilder)
        image_table.search.return_value = mock_query_builder
        image_table.search().select().where().limit().to_list.return_value = []

        builder = TableQueryBuilder(image_table)
        builder.order_by("column1").offset(1).limit(1)

        with pytest.raises(DatasetPaginationError):
            builder.build()
