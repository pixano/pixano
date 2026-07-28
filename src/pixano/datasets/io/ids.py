# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Deterministic id derivation and the cross-flush id ledger.

Ids derive from source identity so re-running an import converges instead of
duplicating (spec §8). Every derived id is prefixed with an 8-character
namespace slug, which makes add-mode rollback expressible as a single
``id LIKE '{prefix}-%'`` delete without journaling individual ids.
"""

from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from pathlib import Path


_BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_NAMESPACE_PREFIX_LENGTH = 8


def _base62(data: bytes) -> str:
    number = int.from_bytes(data, "big")
    if number == 0:
        return _BASE62_ALPHABET[0]
    digits: list[str] = []
    while number:
        number, remainder = divmod(number, 62)
        digits.append(_BASE62_ALPHABET[remainder])
    return "".join(reversed(digits))


def namespace_prefix(namespace: str) -> str:
    """Derive the 8-character id prefix for a namespace (source identity)."""
    digest = hashlib.blake2b(namespace.encode("utf-8"), digest_size=6).digest()
    return _base62(digest).rjust(_NAMESPACE_PREFIX_LENGTH, _BASE62_ALPHABET[0])[:_NAMESPACE_PREFIX_LENGTH]


def stable_id(namespace: str, *parts: str | int) -> str:
    """Derive a deterministic, collision-resistant id from a namespace and parts.

    The hash is length-prefixed over each part, so ``("ab", "c")`` and
    ``("a", "bc")`` never collide. Same inputs always produce the same id —
    across processes and runs — which is what makes imports idempotent and
    resumable.
    """
    hasher = hashlib.blake2b(digest_size=16)
    for part in parts:
        encoded = str(part).encode("utf-8")
        hasher.update(len(encoded).to_bytes(4, "big"))
        hasher.update(encoded)
    return f"{namespace_prefix(namespace)}-{_base62(hasher.digest())}"


class IdLedger:
    """Tracks ids inserted per table across flushes, spilling to SQLite at scale.

    The import engine feeds every flushed batch into the ledger and answers
    uniqueness/foreign-key checks from it — on fresh builds this removes all
    per-flush database scans (spec §8). Past ``spill_threshold`` total ids the
    ledger moves to an on-disk SQLite database to bound memory.
    """

    def __init__(self, spill_dir: Path | None = None, spill_threshold: int = 5_000_000):
        """Initialize an empty ledger.

        Args:
            spill_dir: Directory for the SQLite spill file (a temp dir by default).
            spill_threshold: Total id count beyond which the ledger spills to disk.
        """
        self._spill_dir = spill_dir
        self._spill_threshold = spill_threshold
        self._memory: dict[str, set[str]] = {}
        self._total = 0
        self._connection: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def add(self, table: str, ids: set[str] | list[str]) -> None:
        """Record ids as present in a table."""
        if self._connection is not None:
            self._sql_add(table, ids)
            return

        bucket = self._memory.setdefault(table, set())
        before = len(bucket)
        bucket.update(ids)
        self._total += len(bucket) - before
        if self._total > self._spill_threshold:
            self._spill()

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def contains(self, table: str, id: str) -> bool:
        """Whether an id is known for a table."""
        if self._connection is None:
            return id in self._memory.get(table, set())
        row = self._connection.execute("SELECT 1 FROM ids WHERE tbl = ? AND id = ? LIMIT 1", (table, id)).fetchone()
        return row is not None

    def fk_lookup(self, table: str, ids: set[str]) -> dict[str, bool]:
        """Bulk existence lookup, signature-compatible with `Dataset.find_ids_in_table`."""
        if self._connection is None:
            known = self._memory.get(table, set())
            return {id: id in known for id in ids}

        found: set[str] = set()
        id_list = list(ids)
        chunk_size = 500  # SQLite bound-variable limit safety
        for start in range(0, len(id_list), chunk_size):
            chunk = id_list[start : start + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            rows = self._connection.execute(
                f"SELECT id FROM ids WHERE tbl = ? AND id IN ({placeholders})",  # noqa: S608
                (table, *chunk),
            ).fetchall()
            found.update(row[0] for row in rows)
        return {id: id in found for id in ids}

    def missing(self, table: str, ids: set[str]) -> set[str]:
        """Subset of ids not known for a table."""
        lookup = self.fk_lookup(table, ids)
        return {id for id, is_found in lookup.items() if not is_found}

    def known_ids(self, tables: list[str] | None = None) -> dict[str, set[str]]:
        """Snapshot of in-memory ids per table (pre-spill only; used for small builds)."""
        if self._connection is not None:
            raise RuntimeError("known_ids() is unavailable after the ledger spilled to SQLite; use fk_lookup().")
        table_names = tables if tables is not None else list(self._memory)
        return {table: set(self._memory.get(table, set())) for table in table_names}

    # ------------------------------------------------------------------
    # Spill machinery
    # ------------------------------------------------------------------

    def _spill(self) -> None:
        spill_dir = self._spill_dir if self._spill_dir is not None else Path(tempfile.mkdtemp(prefix="pixano-ledger-"))
        spill_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(spill_dir / "id_ledger.sqlite")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS ids (tbl TEXT NOT NULL, id TEXT NOT NULL, PRIMARY KEY (tbl, id))"
        )
        self._connection = connection
        for table, ids in self._memory.items():
            self._sql_add(table, ids)
        self._memory.clear()

    def _sql_add(self, table: str, ids: set[str] | list[str]) -> None:
        assert self._connection is not None
        self._connection.executemany(
            "INSERT OR IGNORE INTO ids (tbl, id) VALUES (?, ?)",
            ((table, id) for id in ids),
        )
        self._connection.commit()

    def close(self) -> None:
        """Close the SQLite spill connection, if any."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
