# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Per-frame time series with fixed-size vector columns (robot state/action).

One row per (record, frame); each numeric feature is a LanceDB
fixed-size-list column stamped with its dimension at import time (the same
mechanism view embeddings use), so rows align 1:1 with sequence frames and
stay queryable as vectors.
"""

from typing import Any

from lancedb.pydantic import Vector
from pydantic import create_model

from pixano.schemas.records import RecordComponent


class TimeSeries(RecordComponent):
    """Base per-frame time-series row (concrete schemas add Vector columns).

    Attributes:
        view_id: Optional view the series is tied to ("" when record-global).
        frame_id: The matching sequence-frame row id ("" when not linked).
        frame_index: Frame position within the sequence.
        timestamp: Time in seconds (episode-relative for robot datasets).
    """

    view_id: str = ""
    frame_id: str = ""
    frame_index: int = -1
    timestamp: float = -1.0


def create_timeseries_schema(vector_fields: dict[str, int]) -> type[TimeSeries]:
    """Create a concrete TimeSeries schema with one Vector column per feature.

    Args:
        vector_fields: Column name -> fixed vector dimension
            (e.g. ``{"action": 7, "observation_state": 7}``).

    Returns:
        The dynamically created schema class (named ``TimeSeries`` so the
        info.json manifest resolves its canonical base).
    """
    fields: dict[str, Any] = {name: (Vector(dim), ...) for name, dim in vector_fields.items()}
    return create_model("TimeSeries", __base__=TimeSeries, **fields)
