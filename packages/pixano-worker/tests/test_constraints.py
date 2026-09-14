# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Les contraintes du schéma encodent des décisions de conception.

Chaque test ici nomme le défaut qu'une contrainte rend impossible. Ce ne sont pas des tests
de PostgreSQL : ce sont les garde-fous qui empêchent les lots suivants de réintroduire un
problème qu'on a délibérément conçu hors d'atteinte.
"""

import psycopg
import pytest
from pixano_worker.schema import SCHEMA_NAME


def _new_job(db: psycopg.Connection, **fields: object) -> str:
    columns = {"kind": "factice", "dataset": "ds", "total_tasks": 1, **fields}
    names = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    row = db.execute(
        f"INSERT INTO {SCHEMA_NAME}.jobs ({names}) VALUES ({placeholders}) RETURNING id",
        tuple(columns.values()),
    ).fetchone()
    assert row is not None
    return str(row[0])


class TestJobConstraints:
    def test_the_database_generates_the_identifier(self, db: psycopg.Connection) -> None:
        """Ni l'application ni le worker n'ont besoin d'une bibliothèque d'identifiants."""
        assert _new_job(db)

    def test_an_unknown_state_is_refused(self, db: psycopg.Connection) -> None:
        with pytest.raises(psycopg.errors.CheckViolation):
            _new_job(db, state="oops")

    def test_an_error_payload_requires_a_failed_job(self, db: psycopg.Connection) -> None:
        """Le défaut du magasin SQLite : l'annulation planquée dans la charge d'erreur.

        Voir src/pixano/datasets/io/jobs.py:189-207 — `request_cancel` y écrit
        `{"cancel_requested": True}` dans `error_json`, ce qui écrase l'erreur précédente et
        se fait écraser en retour. Ici c'est structurellement impossible.
        """
        with pytest.raises(psycopg.errors.CheckViolation):
            _new_job(db, state="done", error="{}")

    def test_a_cancelled_job_keeps_no_error(self, db: psycopg.Connection) -> None:
        with pytest.raises(psycopg.errors.CheckViolation):
            _new_job(db, state="cancelled", error='{"cancel_requested": true}')

    def test_params_must_be_an_object(self, db: psycopg.Connection) -> None:
        """Un modèle pydantic entre toujours ; un tableau nu, jamais."""
        with pytest.raises(psycopg.errors.CheckViolation):
            _new_job(db, params="[1, 2]")


class TestChunkConstraints:
    def test_a_lease_exists_exactly_while_running(self, db: psycopg.Connection) -> None:
        """Un chunk terminé qui garderait son bail, ou un chunk actif sans bail — donc
        jamais récupérable — sont refusés à l'écriture."""
        job = _new_job(db)

        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute(
                f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, task_count, state) "
                "VALUES (%s, 0, 1, 'running')",
                (job,),
            )

    def test_a_finished_chunk_cannot_keep_its_lease(self, db: psycopg.Connection) -> None:
        job = _new_job(db)

        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute(
                f"INSERT INTO {SCHEMA_NAME}.job_chunks "
                "(job_id, seq, task_count, state, lease_until) "
                "VALUES (%s, 0, 1, 'done', now())",
                (job,),
            )

    def test_the_same_rank_cannot_be_inserted_twice(self, db: psycopg.Connection) -> None:
        """Rend l'insertion des chunks idempotente : un POST rejoué ne double pas le travail."""
        job = _new_job(db)
        db.execute(
            f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, task_count) VALUES (%s, 0, 1)",
            (job,),
        )

        with pytest.raises(psycopg.errors.UniqueViolation):
            db.execute(
                f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, task_count) VALUES (%s, 0, 1)",
                (job,),
            )

    def test_deleting_a_job_takes_its_chunks_and_events(self, db: psycopg.Connection) -> None:
        job = _new_job(db)
        db.execute(
            f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, task_count) VALUES (%s, 0, 1)",
            (job,),
        )
        db.execute(
            f"INSERT INTO {SCHEMA_NAME}.job_events (job_id, type) VALUES (%s, 'state')",
            (job,),
        )

        db.execute(f"DELETE FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job,))

        for table in ("job_chunks", "job_events"):
            row = db.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.{table}").fetchone()
            assert row is not None and row[0] == 0
