# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The SQL this application runs against the job queue.

Gathered in one module on purpose. The application is the *second* client of a database the
worker owns: keeping its statements in one place makes it obvious what it touches — the rows
a user asks for — and what it never touches: the claim, the lease, the progress, and the
schema itself.
"""

SCHEMA_NAME = "pixano_jobs"

# `to_regclass` answers without raising on a database where the worker has never run.
QUEUE_EXISTS = f"SELECT to_regclass('{SCHEMA_NAME}.jobs')"

INSERT_JOB = f"""
INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, params, total_tasks)
VALUES (%s, %s, %s, %s)
RETURNING id, kind, dataset, state, total_tasks, done_tasks, created_at
"""

# `unnest` of parallel arrays inserts every chunk in one statement. Sending them one by one
# would be as many round trips, and a job of 50 000 images is 800 chunks.
INSERT_CHUNKS = f"""
INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, payload, task_count)
SELECT %s, chunk.seq, chunk.payload, chunk.task_count
FROM unnest(%s::int[], %s::jsonb[], %s::int[]) AS chunk(seq, payload, task_count)
"""

SELECT_JOB = f"""
SELECT id, kind, dataset, state, total_tasks, done_tasks, created_at
FROM {SCHEMA_NAME}.jobs WHERE id = %s
"""

LIST_JOBS = f"""
SELECT id, kind, dataset, state, total_tasks, done_tasks, created_at
FROM {SCHEMA_NAME}.jobs ORDER BY created_at DESC LIMIT %s
"""

# Demander l'annulation, sans toucher aux chunks en cours : leur worker les rendra de
# lui-même entre deux lots.
REQUEST_CANCEL = f"""
UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now(), updated_at = now()
WHERE id = %s AND state IN ('pending', 'running') AND cancel_requested_at IS NULL
"""

# Les chunks en attente sortent de la file. C'est ce qui permet à la requête de réclamation
# du worker de ne jamais joindre la table des jobs.
CANCEL_PENDING_CHUNKS = f"""
UPDATE {SCHEMA_NAME}.job_chunks SET state = 'cancelled', updated_at = now()
WHERE job_id = %s AND state = 'pending'
"""

# Un job dont plus rien ne tourne est terminal immédiatement.
SETTLE_IF_IDLE = f"""
UPDATE {SCHEMA_NAME}.jobs SET state = 'cancelled', updated_at = now()
WHERE id = %s AND state IN ('pending', 'running')
  AND NOT EXISTS (
      SELECT 1 FROM {SCHEMA_NAME}.job_chunks
      WHERE job_id = %s AND state = 'running'
  )
"""
