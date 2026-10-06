# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The registry of job kinds, and its declaration in the database.

The registry is local to the worker; the application has no way to import it. This is why
every worker publishes what it can do in `job_kinds` at startup: that table is the only
bridge between the two, and it carries the only truth that counts — what code actually
deployed knows how to run.
"""

import psycopg
from psycopg.types.json import Jsonb

from ..schema import SCHEMA_NAME
from .base import JobKind


DECLARE = f"""
INSERT INTO {SCHEMA_NAME}.job_kinds (name, params_schema, declared_by, declared_at)
VALUES (%s, %s, %s, now())
ON CONFLICT (name) DO UPDATE
SET params_schema = EXCLUDED.params_schema,
    declared_by = EXCLUDED.declared_by,
    declared_at = EXCLUDED.declared_at
"""


class Registry:
    """The job kinds this worker knows how to run."""

    def __init__(self) -> None:
        """Create an empty registry."""
        self._kinds: dict[str, JobKind] = {}

    def register(self, kind: JobKind) -> None:
        """Add a kind to the registry.

        Raises:
            ValueError: A kind already bears this name.
        """
        if kind.name in self._kinds:
            raise ValueError(f"the job kind '{kind.name}' is already registered")
        self._kinds[kind.name] = kind

    def get(self, name: str) -> JobKind | None:
        """The kind bearing this name, or None."""
        return self._kinds.get(name)

    def names(self) -> list[str]:
        """The registered names, sorted."""
        return sorted(self._kinds)

    def declare(self, conn: psycopg.Connection, worker_id: str) -> int:
        """Publish this registry in the database, so that the application can validate.

        The declaration overwrites the previous one: a worker redeployed with modified
        parameters updates the schema without intervention.

        Returns:
            The number of kinds declared.
        """
        with conn.transaction():
            for kind in self._kinds.values():
                conn.execute(DECLARE, (kind.name, Jsonb(kind.params_schema()), worker_id))
        return len(self._kinds)
