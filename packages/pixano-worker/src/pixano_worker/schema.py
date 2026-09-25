# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Installation of the job queue schema.

There is deliberately no migration engine. Until this database holds irreplaceable data —
user accounts, at step 6 — "wipe and recreate" is the migration strategy retained: jobs are
disposable, their results live in LanceDB. This module therefore only applies an idempotent
file and records a version number.

That number is not decoration: `CREATE TABLE IF NOT EXISTS` creates a missing table but never
alters an existing one. Without it, a worker would happily run on a schema that is no longer
its own and fail later, far from the cause. With it, it refuses to start and says what to do.

**Any change to `sql/schema.sql` requires bumping `SCHEMA_VERSION`.**
"""

import logging
from importlib.resources import files

import psycopg


logger = logging.getLogger("pixano-worker")

# Bump on every change to sql/schema.sql.
SCHEMA_VERSION = 5

SCHEMA_NAME = "pixano_jobs"

# NOTIFY channels are global to the database, not to the schema: the prefix avoids a collision
# with what step 6 will add.
NOTIFY_CHANNEL = "pixano_jobs_events"


class SchemaVersionError(RuntimeError):
    """The database holds a schema version this worker does not know how to use."""


def read_schema_sql() -> str:
    """Read the schema file shipped in the package.

    Goes through `importlib.resources` and not a path relative to `__file__`: the image
    installs the package in the venv, where the file is not next to a source tree.
    """
    return files("pixano_worker").joinpath("sql/schema.sql").read_text(encoding="utf-8")


def _installed_version(cursor: psycopg.Cursor) -> int | None:
    """Read the version in the database, or None if the schema was never installed."""
    cursor.execute(f"SELECT to_regclass('{SCHEMA_NAME}.schema_version')")
    row = cursor.fetchone()
    if row is None or row[0] is None:
        return None
    cursor.execute(f"SELECT version FROM {SCHEMA_NAME}.schema_version")
    row = cursor.fetchone()
    return None if row is None else int(row[0])


# `IF NOT EXISTS` is not atomic against a concurrent creator: two workers starting together on
# a blank database both see "the table does not exist", and the second fails at creation.
# PostgreSQL then rolls back its transaction — nothing is applied halfway — and it is enough to
# start over to take the "already installed" branch.
_CONCURRENT_CREATION = (
    psycopg.errors.UniqueViolation,
    psycopg.errors.DuplicateSchema,
    psycopg.errors.DuplicateTable,
    psycopg.errors.DuplicateObject,
)


def ensure_schema(conn: psycopg.Connection) -> None:
    """Install the schema if needed, and check that it is the one this worker expects.

    Args:
        conn: Open PostgreSQL connection.

    Raises:
        SchemaVersionError: The database holds a version other than `SCHEMA_VERSION`. Nothing
            is written in that case: the transaction is rolled back.
    """
    try:
        installed = _install(conn)
    except _CONCURRENT_CREATION:
        logger.info("schema installed at the same instant by another worker — trying again")
        installed = _install(conn)

    if installed is None:
        logger.info("schema %s created (version %s)", SCHEMA_NAME, SCHEMA_VERSION)
    else:
        logger.info("schema %s already at version %s", SCHEMA_NAME, SCHEMA_VERSION)


def _install(conn: psycopg.Connection) -> int | None:
    """Apply the file in one transaction, and return the version found beforehand."""
    with conn.transaction(), conn.cursor() as cursor:
        installed = _installed_version(cursor)

        if installed is not None and installed != SCHEMA_VERSION:
            raise SchemaVersionError(
                f"incompatible database schema: the database holds version {installed}, "
                f"this worker expects version {SCHEMA_VERSION}.\n"
                "No migration is provided at this stage — the job queue holds nothing "
                "irreplaceable, it is recreated empty at the next startup. Drop the schema, "
                "then restart the worker:\n"
                '  psql "$PIXANO_DATABASE_URL" -c "DROP SCHEMA pixano_jobs CASCADE"\n'
                '(With the compose: docker compose exec postgres psql -U pixano -d pixano -c "...", '
                "then docker compose restart pixano-worker — not docker compose down -v, which "
                "would also wipe the downloaded weights of the inference model.)"
            )

        # Replay the file even when the version matches: it is a handful of `IF NOT EXISTS`
        # statements, and it repairs a database from which an index was dropped by hand. It
        # repairs no altered column, however — that is exactly the gap the version number
        # covers.
        cursor.execute(read_schema_sql())  # type: ignore[arg-type]
        cursor.execute(
            f"INSERT INTO {SCHEMA_NAME}.schema_version (version) VALUES (%s) " "ON CONFLICT (singleton) DO NOTHING",
            (SCHEMA_VERSION,),
        )

    return installed
