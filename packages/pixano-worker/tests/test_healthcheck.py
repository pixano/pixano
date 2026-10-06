# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests of the worker's liveness probe."""

import os
import time
from pathlib import Path

import pytest
from pixano_worker.__main__ import MAX_BACKOFF_S, beat
from pixano_worker.config import MAX_HEARTBEAT_AGE_S
from pixano_worker.healthcheck import main as probe


@pytest.fixture
def heartbeat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the heartbeat file to a throwaway location."""
    path = tmp_path / "battement"
    monkeypatch.setenv("PIXANO_WORKER_HEARTBEAT", str(path))
    return path


def test_a_missing_heartbeat_is_unhealthy(heartbeat: Path) -> None:
    """Before the first heartbeat, there is nothing to read: the worker is not ready."""
    assert probe() == 1


def test_a_fresh_heartbeat_is_healthy(heartbeat: Path) -> None:
    beat(str(heartbeat))

    assert probe() == 0


def test_a_stale_heartbeat_is_unhealthy(heartbeat: Path) -> None:
    beat(str(heartbeat))
    stale = time.time() - MAX_HEARTBEAT_AGE_S - 1
    os.utime(heartbeat, (stale, stale))

    assert probe() == 1


def test_beating_again_revives_a_stale_worker(heartbeat: Path) -> None:
    beat(str(heartbeat))
    stale = time.time() - MAX_HEARTBEAT_AGE_S - 1
    os.utime(heartbeat, (stale, stale))

    beat(str(heartbeat))

    assert probe() == 0


def test_the_backoff_cannot_outlast_the_liveness_window() -> None:
    """The worker beats only once per waiting round.

    If the spacing between attempts reached the age limit, a worker waiting for an absent
    dependency would flip to "unhealthy" while doing exactly its job.
    """
    assert MAX_BACKOFF_S < MAX_HEARTBEAT_AGE_S
