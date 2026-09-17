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

# What kinds a worker has declared it can run. The application shares no code with the
# worker, so this table is the only thing that can answer "is this job runnable at all".
SELECT_KIND = f"SELECT params_schema FROM {SCHEMA_NAME}.job_kinds WHERE name = %s"

LIST_KINDS = f"SELECT name, params_schema FROM {SCHEMA_NAME}.job_kinds ORDER BY name"

# The job is recorded without chunks: the worker splits it, because splitting is
# kind-specific logic and kind code only runs on that side.
INSERT_JOB = f"""
INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, params, state)
VALUES (%s, %s, %s, 'planning')
RETURNING id, kind, dataset, state, total_tasks, done_tasks, created_at, 0, 0, 0, false
"""

# What a job's tasks became, next to how many were attempted. Aggregated on read from the
# chunks and the quarantine rather than kept as counters on the job: a counter could drift
# from what it summarises, an aggregate cannot. `done_tasks` alone reports 26 766 / 26 766 on
# a dataset where 404 records carry an image — the outcome is what says so.
_JOB_PROJECTION = f"""
SELECT j.id, j.kind, j.dataset, j.state, j.total_tasks, j.done_tasks, j.created_at,
       coalesce((SELECT sum(c.produced) FROM {SCHEMA_NAME}.job_chunks c
                 WHERE c.job_id = j.id AND c.state = 'done'), 0)::int,
       coalesce((SELECT sum(c.skipped) FROM {SCHEMA_NAME}.job_chunks c
                 WHERE c.job_id = j.id AND c.state = 'done'), 0)::int,
       (SELECT count(*) FROM {SCHEMA_NAME}.job_items i WHERE i.job_id = j.id)::int,
       j.cancel_requested_at IS NOT NULL
FROM {SCHEMA_NAME}.jobs j
"""

SELECT_JOB = _JOB_PROJECTION + "WHERE j.id = %s"

LIST_JOBS = _JOB_PROJECTION + "ORDER BY j.created_at DESC LIMIT %s"

# The quarantine of a job, in the order items were set aside.
LIST_QUARANTINE = f"""
SELECT item_id, reason, detail, created_at
FROM {SCHEMA_NAME}.job_items WHERE job_id = %s
ORDER BY created_at, item_id LIMIT %s
"""

# Demander l'annulation, sans toucher aux chunks en cours : leur worker les rendra de
# lui-même avant le chunk suivant.
REQUEST_CANCEL = f"""
UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now(), updated_at = now()
WHERE id = %s AND state IN ('planning', 'pending', 'running') AND cancel_requested_at IS NULL
"""

# Les chunks en attente sortent de la file. C'est ce qui permet à la requête de réclamation
# du worker de ne jamais joindre la table des jobs.
CANCEL_PENDING_CHUNKS = f"""
UPDATE {SCHEMA_NAME}.job_chunks SET state = 'cancelled', updated_at = now()
WHERE job_id = %s AND state = 'pending'
"""

# Un job dont plus rien ne tourne est terminal immédiatement. Le bail de planification est
# rendu avec l'état : le schéma refuse un bail hors de `planning`, et un job réclamé par un
# planificateur au moment de l'annulation en porte un.
SETTLE_IF_IDLE = f"""
UPDATE {SCHEMA_NAME}.jobs SET state = 'cancelled', planning_until = NULL, updated_at = now()
WHERE id = %s AND state IN ('planning', 'pending', 'running')
  AND NOT EXISTS (
      SELECT 1 FROM {SCHEMA_NAME}.job_chunks
      WHERE job_id = %s AND state = 'running'
  )
"""
