# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Any, TypeVar

import duckdb
import pandas as pd
import polars as pl
import pyarrow as pa
from lancedb.db import LanceTable
from lancedb.query import LanceEmptyQueryBuilder
from typing_extensions import Self

from pixano.features.schemas.base_schema import BaseSchema


T = TypeVar("T", bound=BaseSchema)


class _PixanoEmptyQueryBuilder(LanceEmptyQueryBuilder):
    def __init__(self, arrow_table):
        self._arrow_table = arrow_table

    def to_arrow(self) -> pa.Table:
        return self._arrow_table


class TableQueryBuilder:
    """Builder class for querying LanceTables.

    It supports the select, where, limit, offset, and order_by clauses:
    - The select clause can be used to select specific columns from the table. If not provided, all columns
        are selected.
    - The where clause can be used to filter the rows of the table.
    - The limit clause can be used to limit the number of rows returned.
    - The offset clause can be used to skip the first n rows.
    - The order_by clause can be used to sort the rows of the table.

    The query is built and executed when calling to_pandas(), to_list(), to_pydantic(), or to_polars().

    Attributes:
        table: The LanceTable to query.
    """

    def __init__(self, table: LanceTable):
        """Initializes the TableQueryBuilder.

        Args:
            table: The LanceTable to query.
        """
        if not isinstance(table, LanceTable):
            raise ValueError("table must be a LanceTable.")

        self.table: LanceTable = table
        self._columns: list[str] | dict[str, str] | None = None
        self._where: str | None = None
        self._limit: int | None = None
        self._offset: int | None = None
        self._order_by: list[str] = []
        self._descending: list[bool] = []
        self._function_called: dict[str, bool] = {
            "select": False,
            "where": False,
            "limit": False,
            "offset": False,
            "order_by": False,
            "build": False,
        }

    def _check_called(self, fn_name: str):
        if self._function_called[fn_name]:
            raise ValueError(f"{fn_name}() can only be called once.")
        elif self._function_called["build"]:
            raise ValueError("build() has already been called.")
        self._function_called[fn_name] = True

    def select(self, columns: str | list[str] | dict[str, str]) -> Self:
        """Selects columns to include in the query.

        Note:
            'id' is always included in the select clause.

        Args:
            columns: The columns to include in the query. If a list, the columns are selected in the order they are
                provided. If a dictionary, the keys are the column names and the values are the aliases.
        """
        self._check_called("select")
        if isinstance(columns, str):
            columns = [columns]

        if isinstance(columns, list) or isinstance(columns, dict):
            if isinstance(columns, list) and not all(isinstance(x, str) for x in columns):
                raise ValueError("columns must be a list of strings.")
            elif isinstance(columns, dict) and not all(
                isinstance(k, str) and isinstance(v, str) for k, v in columns.items()
            ):
                raise ValueError("columns must be a dictionary with string keys and values.")
            if isinstance(columns, list) and "id" not in columns:
                columns = ["id"] + columns
            elif isinstance(columns, dict) and "id" not in columns.values():
                columns["id"] = "id"
            self._columns = columns
        else:
            raise ValueError("columns must be a string, a list of string or a string mapping dictionary.")
        return self

    def where(self, where: str) -> Self:
        """Sets the where clause for the query.

        Args:
            where: The condition to filter the rows.

        Returns:
            The TableQueryBuilder instance.
        """
        self._check_called("where")
        if not isinstance(where, str):
            raise ValueError("where must be a string.")
        self._where = where
        return self

    def limit(self, limit: int | None) -> Self:
        """Sets the limit for the query.

        Args:
            limit: The number of rows to return.

        Returns:
            The TableQueryBuilder instance.
        """
        self._check_called("limit")
        if limit is not None:
            if not isinstance(limit, int) or limit < 0:
                raise ValueError("limit must be None or a positive integer.")
        self._limit = limit
        return self

    def offset(self, offset: int | None) -> Self:
        """Sets the offset for the query.

        Args:
            offset: The number of rows to skip.

        Returns:
            The TableQueryBuilder instance.
        """
        self._check_called("offset")
        if offset is not None:
            if not isinstance(offset, int) or offset < 0:
                raise ValueError("offset must be None or a positive integer.")
        self._offset = offset
        return self

    def order_by(self, order_by: str | list[str], descending: bool | list[bool] = False) -> Self:
        """Sets the order_by clause for the query.

        Args:
            order_by: The column(s) to sort by.
            descending: Whether to sort in descending order.

        Returns:
            The TableQueryBuilder instance.
        """
        self._check_called("order_by")
        if isinstance(order_by, str):
            order_by = [order_by]
        elif not isinstance(order_by, list) or not all(isinstance(x, str) for x in order_by):
            raise ValueError("order_by must be a string or a list of strings.")
        if isinstance(descending, bool):
            descending = [descending] * len(order_by)
        elif (
            not isinstance(descending, list)
            or not all(isinstance(x, bool) for x in descending)
            or len(descending) != len(order_by)
        ):
            raise ValueError("descending must be a boolean or a list of booleans with the same length as order_by.")

        self._order_by = order_by
        self._descending = descending
        return self

    def _execute(self) -> pa.Table:
        """Builds the LanceQueryBuilder.

        If order_by or offset are set, the rows are fetched and sorted before building the query.

        Note:
            to_pydantic() and to_list() will call this method internally and keep the order of the rows.

        Returns:
            The LanceQueryBuilder instance if get_order is False, otherwise a tuple with the query and the ordered IDs.
        """
        if all(not self._function_called[fn_name] for fn_name in self._function_called):
            raise ValueError("At least one of select(), where(), limit(), offset(), or order_by() must be called.")
        self._check_called("build")

        if self._columns is None or self._columns == ["*"]:
            # If no columns are selected, select all columns
            # Can have better performance than *
            columns = self.table.schema.names
        else:
            columns = self._columns

        # If order_by
        #   build the query directly using DuckDB
        # Else
        #   build the query using Lance
        # This is because Lance does not support order_by
        # Also DuckDB is less memory efficient than Lance
        if self._order_by != []:
            arrow_table = self.table.to_lance()  # noqa: F841

            def duckdb_format_column(column):
                if "." in column:
                    struct, property = column.split(".")
                    return f"{struct}['{property}']"
                return column

            formatted_columns = [
                duckdb_format_column(col) for col in columns
            ]  # format columns to handle struct columns
            SQL_QUERY = f"SELECT {', '.join(formatted_columns)} FROM arrow_table"
            if self._where is not None:
                SQL_QUERY += f" WHERE {self._where}"
            if self._order_by != []:
                SQL_QUERY += " ORDER BY "
                SQL_QUERY += ", ".join(
                    [f"{col} {'DESC' if desc else 'ASC'}" for col, desc in zip(self._order_by, self._descending)]
                )
            if self._limit is not None:
                SQL_QUERY += f" LIMIT {self._limit}"
            if self._offset is not None:
                SQL_QUERY += f" OFFSET {self._offset}"

            arrow_results: pa.Table = duckdb.query(SQL_QUERY).to_arrow_table()
            arrow_results = arrow_results.rename_columns(columns)  # rename columns to match the requested columns
            return arrow_results
        else:
            limit = self.table.count_rows() if self._limit is None else self._limit
            query = self.table.search(None).select(columns).limit(limit)
            if self._where is not None:
                query = query.where(self._where)
            if self._offset is not None:
                query = query.offset(self._offset)
            return query.to_arrow()

    def to_pandas(self) -> pd.DataFrame:
        """Builds the query and returns the result as a pandas DataFrame.

        Returns:
            The result as a pandas DataFrame.
        """
        return _PixanoEmptyQueryBuilder(self._execute()).to_pandas()

    def to_list(self) -> list[dict[str, Any]]:
        """Builds the query and returns the result as a list of dictionaries.

        Returns:
            The result as a list of dictionaries.
        """
        return _PixanoEmptyQueryBuilder(self._execute()).to_list()

    def to_pydantic(self, model: type[T]) -> list[T]:
        """Builds the query and returns the result as a list of Pydantic models.

        Returns:
            The result as a list of Pydantic models.
        """
        return _PixanoEmptyQueryBuilder(self._execute()).to_pydantic(model)

    def to_polars(self) -> pl.DataFrame:
        """Builds the query and returns the result as a polars DataFrame.

        Returns:
            The result as a polars DataFrame.
        """
        return _PixanoEmptyQueryBuilder(self._execute()).to_polars()
