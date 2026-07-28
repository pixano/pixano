# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Add-mode import manifest: the journal enabling idempotent re-runs and rollback.

Written **before** the first write of an add-mode import (spec §8). Records
the spec/plan fingerprints, the id namespace prefix, and each table's Lance
version before (and, at finalize, after) the import — enough to roll back via
guarded version-restore or namespace-prefix deletion without enumerating ids.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class ImportManifest(BaseModel):
    """Durable description of one add-mode import job's write scope."""

    job_id: str
    dataset_id: str
    spec_fingerprint: str = ""
    plan_fingerprint: str = ""
    id_namespace: str = ""
    ns8_prefix: str = ""
    importer_version: str = ""
    pre_import_versions: dict[str, int] = Field(default_factory=dict)
    post_import_versions: dict[str, int] | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def save(self, path: Path) -> None:
        """Atomically write the manifest (tmp file + rename)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(path.name + ".tmp")
        tmp_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        tmp_path.replace(path)

    @classmethod
    def load(cls, path: Path) -> "ImportManifest":
        """Load a manifest from disk."""
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
