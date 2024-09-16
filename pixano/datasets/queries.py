# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from functools import partial
from typing import Any, Literal, TypeVar, overload

import pandas as pd
import polars as pl
from lancedb.db import LanceTable
from lancedb.query import LanceQueryBuilder
from typing_extensions import Self

from pixano.features.schemas.base_schema import BaseSchema
from pixano.utils.python import fn_sort_dict, to_sql_list

from .utils import DatasetOffsetLimitError


T = TypeVar("T", bound=BaseSchema)


class TableQueryBuilder:
    """Builder for LanceQueryBuilder that handles offset and order_by."""

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
        self._prefilter: bool = False
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

    def select(self, columns: list[str] | dict[str, str]) -> Self:
        """Selects columns to include in the query.

        Note:
            'id' is always included in the select clause.

        Args:
            columns: The columns to include in the query. If a list, the columns are selected in the order they are
            provided. If a dictionary, the keys are the column names and the values are the aliases.
        """
        self._check_called("select")
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
            raise ValueError("columns must be a list or a dictionary.")
        return self

    def where(self, where: str, prefilter: bool = False) -> Self:
        """Sets the where clause for the query."""
        self._check_called("where")
        if not isinstance(where, str):
            raise ValueError("where must be a string.")
        elif not isinstance(prefilter, bool):
            raise ValueError("prefilter must be a boolean.")
        self._where = where
        self._prefilter = prefilter
        return self

    def limit(self, limit: int | None) -> Self:
        """Sets the limit for the query."""
        self._check_called("limit")
        if limit is not None:
            if not isinstance(limit, int) or limit < 0:
                raise ValueError("limit must be None or a positive integer.")
        self._limit = limit
        return self

    def offset(self, offset: int | None) -> Self:
        """Sets the offset for the query."""
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

    @overload
    def build(self, return_ids_sorted: Literal[False] = False) -> LanceQueryBuilder: ...
    @overload
    def build(self, return_ids_sorted: Literal[True]) -> tuple[LanceQueryBuilder, list[str] | None]: ...
    def build(self, return_ids_sorted: bool = False) -> LanceQueryBuilder | tuple[LanceQueryBuilder, list[str] | None]:
        """Builds the LanceQueryBuilder.

        If order_by or offset are set, the rows are fetched and sorted before building the query.

        Note:
            to_pydantic() and to_list() will call this method internally and keep the order of the rows.

        Args:
            return_ids_sorted: Whether to return the ordered IDs. Necessary for sorting the rows outputed by the
            built lance query.

        Returns:
            The LanceQueryBuilder instance if get_order is False, otherwise a tuple with the query and the ordered IDs.
        """
        if all(not self._function_called[fn_name] for fn_name in self._function_called):
            raise ValueError("At least one of select(), where(), limit(), offset(), or order_by() must be called.")
        self._check_called("build")
        has_order_by_or_offset = self._order_by != [] or self._offset not in [None, 0]
        if has_order_by_or_offset:
            select_order = ["id"] + (self._order_by or [])
            query_builder = self.table.search().select(select_order)
            if self._where is not None:
                query_builder = query_builder.where(self._where, self._prefilter)
            rows = query_builder = query_builder.limit(None).to_list()
            if self._order_by != []:
                rows = sorted(
                    rows,
                    key=partial(fn_sort_dict, order_by=self._order_by, descending=self._descending),
                    reverse=False,
                )
            if self._offset is not None:
                rows = rows[self._offset :]
                if self._limit is not None:
                    rows = rows[: self._limit]
            if len(rows) == 0:
                # Have to force empty result to avoid exception
                raise DatasetOffsetLimitError("No results found at this offset")
            ordered_ids = [row["id"] for row in rows]
            sql_ids = to_sql_list(ordered_ids)
            self._where = f"id in {sql_ids}"

        query: LanceQueryBuilder = self.table.search()
        if self._columns is not None:
            query = query.select(self._columns)
        if self._where is not None:
            query = query.where(self._where, self._prefilter)
        query = query.limit(self._limit)  # Pass None to remove the limit

        if return_ids_sorted:
            if not has_order_by_or_offset:
                return query, None
            return query, ordered_ids
        return query

    def to_pandas(self) -> pd.DataFrame:
        """Builds the query and returns the result as a pandas DataFrame.

        Note:
            Cannot be called if build() has already been called.

        Returns:
            The result as a pandas DataFrame.
        """
        query, order = self.build(True)
        df: pd.DataFrame = query.to_pandas()
        if order is not None:
            df.set_index("id", inplace=True)
            df = df.loc[order]
            df.reset_index(inplace=True)
        return df

    def to_list(self) -> list[dict[str, Any]]:
        """Builds the query and returns the result as a list of dictionaries.

        Note:
            Cannot be called if build() has already been called.

        Note:
            Keeps the order of the rows if order_by or offset is set but has to keep 'id' in the select clause.

        Returns:
            The result as a list of dictionaries.
        """
        query, order = self.build(True)
        rows = query.to_list()
        if order is not None:
            ordered_rows = [None for _ in range(len(order))]
            for row in rows:
                idx = order.index(row["id"])
                ordered_rows[idx] = row
            rows = ordered_rows
        return rows

    def to_pydantic(self, model: type[T]) -> list[T]:
        """Builds the query and returns the result as a list of Pydantic models.

        Note:
            Cannot be called if build() has already been called.

        Note:
            Keeps the order of the rows if order_by or offset is set but has to keep 'id' in the select clause.

        Returns:
            The result as a list of Pydantic models.
        """
        query, order = self.build(True)
        rows: list[T] = query.to_pydantic(model)
        if order is not None:
            ordered_rows: list[T] = [None for _ in range(len(order))]  # type: ignore[misc]
            for row in rows:
                idx = order.index(row.id)
                ordered_rows[idx] = row
            rows = ordered_rows
        return rows

    def to_polar(self) -> pl.DataFrame:
        """Builds the query and returns the result as a polars DataFrame.

        Note:
            Cannot be called if build() has already been called.

        Returns:
            The result as a polars DataFrame.
        """
        query, order = self.build(True)
        df: pl.DataFrame = query.to_polars()
        if order is not None:
            order_df = pl.DataFrame({"id": order})
            df = order_df.join(df, on="id", how="left")
        return df
