# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Any, TypeVar

import duckdb
import lancedb
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

    def to_arrow(self, **kwargs) -> pa.Table:
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

    def __init__(self, table: LanceTable, db_connection: lancedb.DBConnection | None = None):
        """Initializes the TableQueryBuilder.

        Args:
            table: The LanceTable to query.
            db_connection: Optional LanceDB connection. Used for count-join queries
                instead of accessing table._conn (private attribute).
        """
        if not isinstance(table, LanceTable):
            raise ValueError("table must be a LanceTable.")

        self.table: LanceTable = table
        self._db_connection: lancedb.DBConnection | None = db_connection
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

        # protection against not allowed columns
        self._order_by = [order for order in self._order_by if order.split(".")[0] in columns or order.startswith("#")]

        # Check if we have a count-join ORDER BY (the #table_name case)
        has_count_join = (
            len(self._order_by) == 1
            and self._order_by[0] not in columns
            and self._order_by[0].startswith("#")
        )

        # Determine if we need the DuckDB path
        needs_duckdb = len(self._order_by) > 0 or (self._offset is not None and self._offset > 0)

        if not needs_duckdb:
            # LanceDB native path — pushes predicates to storage layer, avoids full table materialization
            limit = (self.table.count_rows(self._where) if self._where else self.table.count_rows()) if self._limit is None else self._limit
            query = self.table.search(None).select(columns).limit(limit)
            if self._where is not None:
                query = query.where(self._where)
            return query.to_arrow()
        elif not has_count_join:
            # Optimized path: avoid full table.to_arrow() by fetching bounded set from LanceDB
            # then sorting/slicing with DuckDB over only that subset
            offset = self._offset or 0
            limit = self._limit

            if len(self._order_by) == 0:
                # No ORDER BY, just OFFSET — use LanceDB native with overfetch + slice
                fetch_limit = offset + limit if limit is not None else self.table.count_rows()
                query = self.table.search(None).select(columns).limit(fetch_limit)
                if self._where is not None:
                    query = query.where(self._where)
                arrow_table = query.to_arrow()
                return arrow_table.slice(offset, limit) if offset > 0 else arrow_table
            else:
                # ORDER BY on a regular column — need to fetch all matching rows, sort, then slice
                # But we only fetch the columns we need via LanceDB native (no full to_arrow())
                total = self.table.count_rows(self._where) if self._where is not None else self.table.count_rows()
                query = self.table.search(None).select(columns).limit(total)
                if self._where is not None:
                    query = query.where(self._where)
                arrow_table = query.to_arrow()  # noqa: F841

                def duckdb_format_column(column):
                    if "." in column:
                        struct, prop = column.split(".")
                        return f"{struct}['{prop}']"
                    return column

                formatted_columns = [
                    "arrow_table." + duckdb_format_column(col) for col in columns
                ]
                SQL_QUERY = f"SELECT {', '.join(formatted_columns)} FROM arrow_table"
                SQL_QUERY += " ORDER BY "
                SQL_QUERY += ", ".join(
                    [f"{col} {'DESC' if desc else 'ASC'}" for col, desc in zip(self._order_by, self._descending)]
                )
                if limit is not None:
                    SQL_QUERY += f" LIMIT {limit}"
                if offset > 0:
                    SQL_QUERY += f" OFFSET {offset}"

                arrow_results: pa.Table = duckdb.query(SQL_QUERY).to_arrow_table()
                arrow_results = arrow_results.rename_columns(columns)
                return arrow_results
        else:
            # Count-join path — fetch only needed columns via LanceDB native, then JOIN with count table in DuckDB
            count_table = None  # noqa: F841
            db = self._db_connection if self._db_connection is not None else lancedb.connect(self.table._conn.uri)
            count_name = self._order_by[0][1:]
            if count_name in db.table_names():
                count_tbl = db.open_table(count_name)
                count_table = count_tbl.search(None).select(["item_ref.id"]).limit(  # noqa: F841
                    count_tbl.count_rows()
                ).to_arrow()
                SQL_WITH = """WITH counts AS(
                SELECT "item_ref.id" as id, COUNT(*) as tbl_count FROM count_table GROUP BY "item_ref.id")"""
                self._order_by = ["IFNULL(c.tbl_count, 0)"]
            else:
                self._order_by = []

            # Fetch only needed columns from the item table, respecting WHERE filter
            total = self.table.count_rows(self._where) if self._where else self.table.count_rows()
            query = self.table.search(None).select(columns).limit(total)
            if self._where is not None:
                query = query.where(self._where)
            arrow_table = query.to_arrow()  # noqa: F841

            def duckdb_format_column(column):
                if "." in column:
                    struct, prop = column.split(".")
                    return f"{struct}['{prop}']"
                return column

            formatted_columns = [
                "arrow_table." + duckdb_format_column(col) for col in columns
            ]
            SQL_QUERY = f"SELECT {', '.join(formatted_columns)} FROM arrow_table"
            if count_table is not None:
                SQL_QUERY = SQL_WITH + " " + SQL_QUERY + " LEFT JOIN counts c ON arrow_table.id = c.id"
            # WHERE already applied via LanceDB native filter above
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
            arrow_results = arrow_results.rename_columns(columns)
            return arrow_results

    def to_arrow(self) -> pa.Table:
        """Builds the query and returns the result as a PyArrow Table.

        Returns:
            The result as a PyArrow Table.
        """
        return self._execute()

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
