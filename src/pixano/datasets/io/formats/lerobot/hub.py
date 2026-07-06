# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Hugging Face Hub materialization for LeRobot sources (spec §7.3).

A hub source downloads lazily and minimally: analyze fetches ``meta/**``
only (fast — a few small files); ingest then fetches exactly the video
shards the selected episodes reference. Everything lands in the standard
huggingface_hub cache, so re-runs and other tools share the download.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...errors import MetadataError


_HUB_ID = re.compile(r"^[\w.-]+/[\w.-]+$")


def is_hub_id(source: str) -> bool:
    """True for a bare `org/name` Hub dataset id (and not an existing local path)."""
    return bool(_HUB_ID.match(source)) and not Path(source).exists()


def _require_hf_hub():
    try:
        import huggingface_hub

        return huggingface_hub
    except ImportError:
        raise MetadataError(
            "Importing from the Hugging Face Hub needs huggingface_hub: pip install pixano[lerobot]"
        ) from None


def materialize_meta(repo_id: str, revision: str | None = None) -> Path:
    """Download (or reuse from cache) the dataset's meta/ files; returns the snapshot root."""
    hf_hub = _require_hf_hub()
    try:
        snapshot = hf_hub.snapshot_download(
            repo_id, repo_type="dataset", revision=revision, allow_patterns=["meta/**"]
        )
    except Exception as exc:
        raise MetadataError(f"Could not fetch '{repo_id}' from the Hugging Face Hub: {exc}") from None
    return Path(snapshot)


def materialize_files(repo_id: str, relative_paths: list[str], revision: str | None = None) -> Path:
    """Download specific files (video shards) into the same snapshot; returns its root."""
    hf_hub = _require_hf_hub()
    try:
        snapshot = hf_hub.snapshot_download(
            repo_id, repo_type="dataset", revision=revision, allow_patterns=sorted(set(relative_paths))
        )
    except Exception as exc:
        raise MetadataError(f"Could not fetch media of '{repo_id}' from the Hugging Face Hub: {exc}") from None
    return Path(snapshot)
