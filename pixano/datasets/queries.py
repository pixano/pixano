# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from lancedb.db import LanceTable
from lancedb.query import LanceQueryBuilder
from typing_extensions import Self

from pixano.utils.python import to_sql_list

from .utils import DatasetOffsetLimitError


class TableQueryBuilder:
    """Builder for LanceQueryBuilder that handles offset and order_by."""

    def __init__(self, table: LanceTable):
        """Initializes the TableQueryBuilder.

        Args:
            table: The LanceTable to query.
        """
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
        """Selects columns to include in the query."""
        self._check_called("select")
        if isinstance(columns, list) or isinstance(columns, dict):
            if isinstance(columns, list) and not all(isinstance(x, str) for x in columns):
                raise ValueError("columns must be a list of strings.")
            elif isinstance(columns, dict) and not all(
                isinstance(k, str) and isinstance(v, str) for k, v in columns.items()
            ):
                raise ValueError("columns must be a dictionary with string keys and values.")
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
            raise ValueError("order_by must be a string or a list of strings")
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

    def build(self) -> LanceQueryBuilder:
        """Builds the LanceQueryBuilder.

        If order_by or offset are set, the rows are fetched and sorted before building the query.

        Returns:
            The LanceQueryBuilder instance.
        """
        self._check_called("build")
        if all(not self._function_called[fn_name] for fn_name in self._function_called):
            raise ValueError("At least one of select(), where(), limit(), offset(), or order_by() must be called.")
        has_order_by_or_offset = self._order_by != [] or self._offset not in [None, 0]
        if has_order_by_or_offset:
            select_order = ["id"] + (self._order_by or [])
            ordered_rows = (
                self.table.search().select(select_order).where(self._where, self._prefilter).limit(None).to_list()
            )
            if self._order_by != []:
                ordered_rows.sort(
                    key=lambda x: tuple(
                        x.get(col) if not desc else -(x.get(col))
                        for col, desc in zip(self._order_by, self._descending, strict=True)
                    ),
                    reverse=False,
                )
            if self._offset is not None:
                ordered_rows = ordered_rows[self._offset :]
                if self._limit is not None:
                    ordered_rows = ordered_rows[: self._limit]
            if len(ordered_rows) == 0:
                # Have to force empty result to avoid exception
                raise DatasetOffsetLimitError("No results found at this offset")
            ordered_ids = [row["id"] for row in ordered_rows]
            sql_ids = to_sql_list(ordered_ids)
            self._where = f"id in {sql_ids}"

        query: LanceQueryBuilder = self.table.search()
        if self._columns is not None:
            query = query.select(self._columns)
        if self._where is not None:
            query = query.where(self._where, self._prefilter)
        query = query.limit(self._limit)  # Pass None to remove the limit
        return query
