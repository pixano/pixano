# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Records ordered by how many rows of another table they hold."""

from pathlib import Path

import lancedb
import pyarrow as pa

from pixano.datasets.queries import TableQueryBuilder


# How many tables LanceDB's `table_names()` lists unless told otherwise.
LISTING_PAGE = 10


def test_orders_by_the_count_of_a_table_listed_after_the_first_ten(tmp_path: Path) -> None:
    db = lancedb.connect(tmp_path)
    # Tables named to sort before the counted one, so that it is not among the first ten listed.
    for index in range(LISTING_PAGE):
        db.create_table(f"a{index:02d}", schema=pa.schema([pa.field("id", pa.string())]))
    records = db.create_table("records", data=[{"id": "r1"}, {"id": "r2"}, {"id": "r3"}])
    db.create_table(
        "texts",
        data=[{"id": "t1", "record_id": "r2"}, {"id": "t2", "record_id": "r2"}, {"id": "t3", "record_id": "r3"}],
    )

    rows = TableQueryBuilder(records, db_connection=db).select(["id"]).order_by("#texts", descending=True).to_list()

    assert [row["id"] for row in rows] == ["r2", "r3", "r1"]
