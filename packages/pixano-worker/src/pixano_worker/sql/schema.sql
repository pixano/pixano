-- =====================================
-- Copyright: CEA-LIST/DIASI/SIALV/LVA
-- Author : pixano@cea.fr
-- License: CECILL-C
-- =====================================

-- Schema of the processing subsystem: the job queue, the execution state and the progress
-- events. See docs/specs/backend-processing.md.
--
-- This file is idempotent and takes NO parameter. The two properties are linked: psycopg only
-- accepts several statements in a single execute() when there is no parameter (the extended
-- protocol, used as soon as a value is passed, forbids it). The version number is therefore
-- not written here — it lives in SCHEMA_VERSION, on the Python side, and a single source
-- cannot diverge from itself.

-- The queue does not mix with `public`, where step 6 will put accounts and access rights.
CREATE SCHEMA IF NOT EXISTS pixano_jobs;

-- Version marker. The boolean primary key constrained to `true` makes a second row
-- impossible: reading it can never be ambiguous.
CREATE TABLE IF NOT EXISTS pixano_jobs.schema_version (
    singleton  boolean     PRIMARY KEY DEFAULT true CHECK (singleton),
    version    integer     NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

-- What the workers know how to execute. Each declares its registry here at startup: this is
-- the source of truth for the application, which has no other way of knowing whether a job
-- kind exists — it shares no code with the worker. The question asked at submission is "is
-- there a worker able to do this", not "is this string known".
CREATE TABLE IF NOT EXISTS pixano_jobs.job_kinds (
    name          text        PRIMARY KEY CHECK (name <> ''),
    -- The JSON schema of the kind's parameters, published from its pydantic model. It lets
    -- the application refuse invalid parameters at submission rather than queue a job that
    -- will fail at execution.
    params_schema jsonb       NOT NULL DEFAULT '{}'::jsonb
                              CHECK (jsonb_typeof(params_schema) = 'object'),
    declared_by   text        NOT NULL,
    declared_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pixano_jobs.jobs (
    -- The identifier is produced by the database: neither the application nor the worker
    -- needs an identifier library to create a job.
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    kind                text        NOT NULL CHECK (kind <> ''),
    dataset             text        NOT NULL CHECK (dataset <> ''),
    params              jsonb       NOT NULL DEFAULT '{}'::jsonb
                                    CHECK (jsonb_typeof(params) = 'object'),
    state               text        NOT NULL DEFAULT 'planning',
    -- Cancellation has its own column. The instant is free and also answers "when was it
    -- requested?"; `IS NOT NULL` stands in for a boolean.
    cancel_requested_at timestamptz,
    -- The planning lease. A job stays in `planning` while a worker splits it up; if that
    -- worker dies, the lease expires and another takes the split over. Without it, a job whose
    -- planner went down stayed "running" forever, without a single chunk.
    planning_until      timestamptz,
    total_tasks         integer     NOT NULL DEFAULT 0 CHECK (total_tasks >= 0),
    done_tasks          integer     NOT NULL DEFAULT 0 CHECK (done_tasks >= 0),
    error               jsonb       CHECK (error IS NULL OR jsonb_typeof(error) = 'object'),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    -- `planning` precedes `pending`: the application records the request, the worker runs the
    -- kind's planner and inserts the chunks. Splitting by video or by image is job-kind logic,
    -- which only runs on the worker side.
    CONSTRAINT jobs_state_valid
        CHECK (state IN ('planning', 'pending', 'running', 'done', 'error', 'cancelled')),
    -- A cancellation structurally cannot be written into the error payload: the SQLite
    -- store's flaw is forbidden by a constraint, not by a convention.
    CONSTRAINT jobs_error_only_when_failed
        CHECK (error IS NULL OR state = 'error'),
    -- A planning lease only makes sense during planning.
    CONSTRAINT jobs_planning_lease_only_when_planning
        CHECK (planning_until IS NULL OR state = 'planning')
);

CREATE TABLE IF NOT EXISTS pixano_jobs.job_chunks (
    -- Integer and not uuid: the claim index will carry millions of entries, and increasing
    -- identifiers give it a natural FIFO order as a bonus.
    id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id      uuid        NOT NULL REFERENCES pixano_jobs.jobs (id) ON DELETE CASCADE,
    seq         integer     NOT NULL CHECK (seq >= 0),
    -- What the job kind must process, in a form the engine does not interpret.
    payload     jsonb       NOT NULL DEFAULT '{}'::jsonb
                                    CHECK (jsonb_typeof(payload) = 'object'),
    task_count  integer     NOT NULL CHECK (task_count > 0),
    state       text        NOT NULL DEFAULT 'pending',
    -- Serves two purposes: bounding the recoveries of a chunk that kills its worker, and
    -- serving as a fencing token — a write carries the `attempts` it claimed, so a worker
    -- whose lease expired cannot overwrite its successor's result.
    attempts    integer     NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    -- A retried job (POST /jobs/{id}/retry) reopens its failed chunks without touching
    -- `attempts`, which must stay monotonic to serve as a fencing token: the floor marks where
    -- the count starts over from, and the caps compare `attempts - attempts_floor`.
    attempts_floor integer  NOT NULL DEFAULT 0 CHECK (attempts_floor >= 0 AND attempts_floor <= attempts),
    claimed_by  text,
    lease_until timestamptz,
    -- A transient failure returns the chunk to the queue, but not right away: replayed within
    -- the second against an inference that is restarting, it would use up its attempts before
    -- it came back. Claimable only once this instant has passed.
    available_at timestamptz NOT NULL DEFAULT now(),
    -- The last error, including that of an attempt which will be replayed: it is what we want
    -- to read when a chunk comes back to the queue for the third time.
    error       jsonb       CHECK (error IS NULL OR jsonb_typeof(error) = 'object'),
    -- The outcome of a finished chunk. A task is either produced, or skipped because it is not
    -- applicable (a record without an image for a computation on images), or quarantined in
    -- `job_items`. Without these counts, a job can only say what it attempted, never what it
    -- produced.
    produced    integer     CHECK (produced IS NULL OR produced >= 0),
    skipped     integer     CHECK (skipped IS NULL OR skipped >= 0),
    updated_at  timestamptz NOT NULL DEFAULT now(),

    -- `cancelled` exists so that the claim query never has to join `jobs`: cancelling a job
    -- flips its pending chunks, which takes them out of the partial index.
    CONSTRAINT chunks_state_valid
        CHECK (state IN ('pending', 'running', 'done', 'error', 'cancelled')),
    -- Makes inserting a job's chunks idempotent: a replayed POST does not double the work.
    CONSTRAINT chunks_unique_seq UNIQUE (job_id, seq),
    -- A lease exists exactly during execution. A `done` that forgot to clear its own, or a
    -- `running` without a lease — hence never recoverable — are refused at write time.
    CONSTRAINT chunks_lease_matches_state
        CHECK ((state = 'running') = (lease_until IS NOT NULL)),
    -- The outcome only exists for a finished chunk: a replayed chunk does not keep that of a
    -- previous attempt.
    CONSTRAINT chunks_outcome_only_when_done
        CHECK ((state = 'done') = (produced IS NOT NULL AND skipped IS NOT NULL))
);

-- The quarantine: the items a job kind could not process, one per row. Only failures go in —
-- an item that is not applicable is counted in `skipped`, not stored here, otherwise a lidar
-- dataset would fill the quarantine with readings that are not errors.
-- A table rather than a field of the chunk, because a quarantine must be readable afterwards:
-- "which items of this job failed, and why", to fix or replay them.
CREATE TABLE IF NOT EXISTS pixano_jobs.job_items (
    job_id     uuid        NOT NULL REFERENCES pixano_jobs.jobs (id) ON DELETE CASCADE,
    chunk_id   bigint      NOT NULL REFERENCES pixano_jobs.job_chunks (id) ON DELETE CASCADE,
    -- The item's identifier in the dataset, as the job kind designates it.
    item_id    text        NOT NULL CHECK (item_id <> ''),
    reason     text        NOT NULL CHECK (reason <> ''),
    detail     jsonb       CHECK (detail IS NULL OR jsonb_typeof(detail) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    -- An item is quarantined only once per job: a chunk replayed after its worker's death
    -- replaces the row instead of doubling it.
    PRIMARY KEY (job_id, item_id)
);

-- The journal an interface re-reads when it reconnects. NOTIFY only rings the doorbell: its
-- payload is capped at 8 KB and is only delivered to the clients connected at the moment of
-- the commit.
CREATE TABLE IF NOT EXISTS pixano_jobs.job_events (
    id         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id     uuid        NOT NULL REFERENCES pixano_jobs.jobs (id) ON DELETE CASCADE,
    type       text        NOT NULL CHECK (type IN ('state', 'progress')),
    payload    jsonb       NOT NULL DEFAULT '{}'::jsonb
                                   CHECK (jsonb_typeof(payload) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Claiming: the index carries only the chunks still to do, and shrinks as the work advances
-- while the table, for its part, keeps everything. The key is `id`, exactly the ORDER BY of
-- the query, so the scan is ordered and SKIP LOCKED moves on without re-sorting.
CREATE INDEX IF NOT EXISTS job_chunks_pending_idx
    ON pixano_jobs.job_chunks (id) WHERE state = 'pending';

-- Recovery of expired leases. The "running" set is bounded by the number of workers times the
-- batch size: the index stays tiny.
CREATE INDEX IF NOT EXISTS job_chunks_expired_lease_idx
    ON pixano_jobs.job_chunks (lease_until) WHERE state = 'running';

-- The jobs the worker still has to split up. The set is tiny and drains on its own.
CREATE INDEX IF NOT EXISTS jobs_to_plan_idx
    ON pixano_jobs.jobs (created_at) WHERE state = 'planning';

-- Job list in the interface.
CREATE INDEX IF NOT EXISTS jobs_created_at_idx
    ON pixano_jobs.jobs (created_at DESC);

-- Catching up on an event stream: WHERE job_id = ? AND id > ? ORDER BY id.
CREATE INDEX IF NOT EXISTS job_events_job_idx
    ON pixano_jobs.job_events (job_id, id);
