# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from lancedb.db import LanceTable
from lancedb.query import LanceQueryBuilder
from typing_extensions import Self


class TableQueryBuilder:
    """Builder for LanceQueryBuilder that handles offset and order_by."""

    def __init__(self, table: LanceTable):
        """Initializes the TableQueryBuilder.

        Args:
            table: The LanceTable to query.
        """
        self.table = table
        self._columns: list[str] | dict[str, str] | None = None
        self._where: str | None = None
        self._prefilter: bool = False
        self._limit: int | None = None
        self._offset: int | None = None
        self._order_by: list[str] = []

    def select(self, columns: list[str] | dict[str, str]) -> Self:
        """Selects columns to include in the query."""
        if isinstance(columns, list) or isinstance(columns, dict):
            self._columns = columns
        else:
            raise ValueError("columns must be a list or a dictionary")
        return self

    def where(self, where: str, prefilter: bool = False) -> Self:
        """Sets the where clause for the query."""
        self._where = where
        self._prefilter = prefilter
        return self

    def limit(self, limit: int | None) -> Self:
        """Sets the limit for the query."""
        if limit is not None:
            if not isinstance(limit, int) or limit < 0:
                raise ValueError("limit must be None or a positive integer")
        self._limit = limit
        return self

    def offset(self, offset: int | None) -> Self:
        """Sets the offset for the query."""
        if offset is not None:
            if not isinstance(offset, int) or offset < 0:
                raise ValueError("offset must be None or a positive integer")
        self._offset = offset
        return self

    def order_by(self, order_by: str | list[str]) -> Self:
        """Sets the order_by clause for the query."""
        if isinstance(order_by, str):
            order_by = [order_by]
        elif not isinstance(order_by, list) or not all(isinstance(x, str) for x in order_by):
            raise ValueError("order_by must be a string or a list of strings")
        self._order_by = order_by
        return self

    def build(self) -> LanceQueryBuilder:
        """Builds the LanceQueryBuilder.

        If order_by or offset are set, the rows are fetched and sorted before building the query.

        Returns:
            The LanceQueryBuilder instance.
        """
        has_order_by_or_offset = self._order_by != [] or self._offset not in [None, 0]
        if has_order_by_or_offset:
            select_order = ["id"] + (self._order_by or [])
            ordered_rows = (
                self.table.search().select(select_order).where(self._where, self._prefilter).limit(None).to_list()
            )
            if self._order_by is not None:
                ordered_rows.sort(key=lambda x: tuple(x.get(col) for col in self._order_by))
            if self._offset is not None:
                ordered_rows = ordered_rows[self._offset :]
                if self._limit is not None:
                    ordered_rows = ordered_rows[: self._limit]
            if len(ordered_rows) == 0:
                # Have to force empty result to avoid exception
                self._where = "id != id"
            else:
                ordered_ids = [row["id"] for row in ordered_rows]
                sql_ids = f"('{ordered_ids[0]}')" if len(ordered_ids) == 1 else str(tuple(ordered_ids))
                self._where = f"id in {sql_ids}"

        query: LanceQueryBuilder = self.table.search()
        if self._columns is not None:
            query = query.select(self._columns)
        if self._where is not None:
            query = query.where(self._where, self._prefilter)
        if self._limit is not None:
            query = query.limit(self._limit)
        else:
            query = query.limit(None)
        return query
