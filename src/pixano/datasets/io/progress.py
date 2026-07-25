# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""One progress-event stream for both CLI (tqdm) and job-store (GUI polling) consumers."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field


Phase = Literal["analyze", "ingest", "embed", "finalize"]


class ProgressEvent(BaseModel):
    """One progress observation emitted by the import engine."""

    phase: Phase
    done: int = 0
    total: int | None = None
    unit: str = "records"
    table_counts: dict[str, int] = Field(default_factory=dict)
    message: str = ""
    final: bool = False


class ProgressSink(ABC):
    """Consumer of progress events."""

    @abstractmethod
    def emit(self, event: ProgressEvent) -> None:
        """Handle one progress event."""
        ...

    def close(self) -> None:
        """Release any display/storage resources."""


class TqdmSink(ProgressSink):
    """Renders progress as one tqdm bar per phase, with real totals when known."""

    def __init__(self) -> None:
        """Initialize with no active bar."""
        self._bars: dict[Phase, "object"] = {}

    def emit(self, event: ProgressEvent) -> None:
        """Update (or create) the bar for the event's phase."""
        import tqdm

        bar = self._bars.get(event.phase)
        if bar is None:
            bar = tqdm.tqdm(total=event.total, desc=event.phase, unit=f" {event.unit}")
            self._bars[event.phase] = bar
        if event.total is not None and bar.total != event.total:  # type: ignore[attr-defined]
            bar.total = event.total  # type: ignore[attr-defined]
        bar.n = event.done  # type: ignore[attr-defined]
        if event.message:
            bar.set_postfix_str(event.message, refresh=False)  # type: ignore[attr-defined]
        bar.refresh()  # type: ignore[attr-defined]
        if event.final:
            bar.close()  # type: ignore[attr-defined]
            self._bars.pop(event.phase, None)

    def close(self) -> None:
        """Close all open bars."""
        for bar in self._bars.values():
            bar.close()  # type: ignore[attr-defined]
        self._bars.clear()


class ThrottledSink(ProgressSink):
    """Forwards events to an inner sink at most once per interval.

    Terminal events (``final=True``) are always forwarded so consumers never
    miss completion. Used to bound job-store write frequency (spec §8).
    """

    def __init__(self, inner: ProgressSink, min_interval: float = 0.5):
        """Wrap `inner`, forwarding at most one event per `min_interval` seconds."""
        self._inner = inner
        self._min_interval = min_interval
        # -inf so the first event always forwards: time.monotonic() has an
        # arbitrary epoch (e.g. host uptime) and can be smaller than the interval.
        self._last_emit = float("-inf")

    def emit(self, event: ProgressEvent) -> None:
        """Forward the event if the interval elapsed or the event is terminal."""
        now = time.monotonic()
        if event.final or (now - self._last_emit) >= self._min_interval:
            self._last_emit = now
            self._inner.emit(event)

    def close(self) -> None:
        """Close the wrapped sink."""
        self._inner.close()
