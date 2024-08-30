# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from pixano.app.models.datasets import ColDesc, DatasetExplorer, PaginationInfo, TableData


class TestDatasetExplorer:
    def test_init(self):
        DatasetExplorer(
            id="voc",
            name="pascal",
            table_data=TableData(cols=[ColDesc(name="col", type="col")], rows=[{"metadata": 123}]),
            pagination=PaginationInfo(current=1, size=10, total=20),
            sem_search=["search1", "search2"],
        )
