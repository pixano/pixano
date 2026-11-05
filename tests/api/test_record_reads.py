# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Reading the explorer's records under one request: what a failure is answered."""

import pytest
from fastapi import HTTPException

from pixano.api import record_reads
from pixano.api.query import RecordQuery
from pixano.datasets.queries.record_statistics import InvalidRecordFilter, RecordOrder, StatisticsFilter


SORTED_ON_A_STATISTIC = RecordQuery(
    where="(split = = 'x')",
    index_servable=True,
    statistics_filter=StatisticsFilter(sql='s."bbox_count" >= 1', columns=("bbox_count",)),
    order=RecordOrder(column="bbox_count", descending=True, on_statistics=True),
)


def _failing(error: Exception):
    def read(*_args, **_kwargs):
        raise error

    return read


@pytest.mark.parametrize("read", ["neighbors", "matching"])
def test_a_raw_condition_lance_refuses_is_bad_input(monkeypatch, read: str) -> None:
    monkeypatch.setattr(record_reads, "record_neighbors", _failing(InvalidRecordFilter("unexpected '='")))
    monkeypatch.setattr(record_reads, "matching_record_ids", _failing(InvalidRecordFilter("unexpected '='")))

    with pytest.raises(HTTPException) as refused:
        if read == "neighbors":
            record_reads.read_neighbors(None, SORTED_ON_A_STATISTIC, "r1", raw_where=True)
        else:
            record_reads.read_matching_ids(None, SORTED_ON_A_STATISTIC, raw_where=True)

    assert refused.value.status_code == 400


@pytest.mark.parametrize("read", ["neighbors", "matching"])
def test_a_failure_of_the_server_is_not_answered_as_bad_input(monkeypatch, read: str) -> None:
    """A raw condition does not make every failure its own: reading the statistics may fail too."""
    monkeypatch.setattr(record_reads, "record_neighbors", _failing(RuntimeError("lance error")))
    monkeypatch.setattr(record_reads, "matching_record_ids", _failing(RuntimeError("lance error")))

    with pytest.raises(RuntimeError, match="lance error"):
        if read == "neighbors":
            record_reads.read_neighbors(None, SORTED_ON_A_STATISTIC, "r1", raw_where=True)
        else:
            record_reads.read_matching_ids(None, SORTED_ON_A_STATISTIC, raw_where=True)
