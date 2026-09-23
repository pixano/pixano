# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Conservative source identities for reviewed plans and durable import cursors."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from .errors import PlanMismatchError


def local_source_fingerprint(root: Path, dependencies: Iterable[Path] = ()) -> str:
    """Fingerprint a source tree and referenced files without reading media bytes.

    Paths, sizes, nanosecond modification/change times, and file identities detect
    additions, removals, replacements, and normal in-place edits. Access times are
    excluded so reading a source does not invalidate it. External media references
    and symlink targets are included. Unreadable or cyclic trees are unverifiable.
    This is a filesystem change guard, not a cryptographic media-integrity check.
    """
    digest = hashlib.sha256()

    def add(path: Path, ancestors: frozenset[Path] = frozenset()) -> None:
        resolved = path.resolve(strict=True)
        stat = path.stat()
        is_dir = path.is_dir()
        # Directory timestamps change when unrelated tools create/delete temporary
        # files; the sorted inventory itself captures additions and removals.
        identity = (
            str(path.absolute()),
            str(resolved),
            stat.st_mode,
            stat.st_dev,
            stat.st_ino,
            None if is_dir else stat.st_size,
            None if is_dir else stat.st_mtime_ns,
            None if is_dir else stat.st_ctime_ns,
        )
        digest.update(json.dumps(identity, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
        if is_dir:
            if resolved in ancestors:
                raise ValueError("cyclic source directory")
            for child in sorted(path.iterdir()):
                add(child, ancestors | {resolved})

    try:
        add(root)
        for dependency in dependencies:
            add(dependency)
    except (OSError, ValueError, RuntimeError):
        return ""
    return f"local-v1:{digest.hexdigest()}"


def verify_import_source(
    state_dir: Path,
    job_id: str,
    *,
    source_fingerprint: str,
    spec_fingerprint: str,
    importer: str,
    importer_version: str,
    resume: bool,
) -> None:
    """Bind a cursor to its original inputs before the engine opens any dataset."""
    path = state_dir / "sources" / f"{job_id}.json"
    expected = {
        "source_fingerprint": source_fingerprint,
        "spec_fingerprint": spec_fingerprint,
        "importer": importer,
        "importer_version": importer_version,
    }
    if resume or path.exists():
        try:
            original = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise PlanMismatchError(
                "This import has no verifiable source checkpoint; restart the import instead of resuming."
            ) from None
        if not source_fingerprint or not isinstance(original, dict) or not original.get("source_fingerprint"):
            raise PlanMismatchError("This import's source cannot be verified; restart the import instead of resuming.")
        if original != expected:
            raise PlanMismatchError(
                "The source, import settings, or importer changed after this job started; "
                "restart the import instead of resuming."
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never replace an earlier job's identity. A torn initial write is rejected
    # on resume, before any previously committed dataset rows can be touched.
    with path.open("x", encoding="utf-8") as handle:
        json.dump(expected, handle)
