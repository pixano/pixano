# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests de la sonde de vivacité du worker."""

import os
import time
from pathlib import Path

import pytest
from pixano_worker.__main__ import MAX_BACKOFF_S, beat
from pixano_worker.config import MAX_HEARTBEAT_AGE_S
from pixano_worker.healthcheck import main as probe


@pytest.fixture
def heartbeat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Rediriger le fichier de battement vers un emplacement jetable."""
    path = tmp_path / "battement"
    monkeypatch.setenv("PIXANO_WORKER_HEARTBEAT", str(path))
    return path


def test_a_missing_heartbeat_is_unhealthy(heartbeat: Path) -> None:
    """Avant le premier battement, il n'y a rien à lire : le worker n'est pas prêt."""
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
    """Le worker ne bat qu'une fois par tour d'attente.

    Si l'espacement des tentatives atteignait la limite d'âge, un worker en train d'attendre
    une dépendance absente basculerait « unhealthy » alors qu'il fait exactement son travail.
    """
    assert MAX_BACKOFF_S < MAX_HEARTBEAT_AGE_S
