# Worker and jobs

**Status:** Draft
**Owner:** @vmulet-benzo
**Last agreed change:** 2026-11-25
**Covers:** `packages/pixano-worker/`, `src/pixano/api/jobs/`, `src/pixano/api/routers/jobs.py`, `src/pixano/statistics/`

## Purpose and concepts

Pixano runs long work over a whole dataset as jobs: embeddings, detection, segmentation, video tracking, statistics. A job runs in `pixano-worker`, in the background, while people keep annotating in the interface. The app records the request, the worker splits it and runs it, and the interface follows its progress.

This spec covers the queue of jobs in PostgreSQL, the worker process, the routes of the app that submit and follow jobs, what the follow-ups of an import become on the queue (`src/pixano/api/jobs/follow_ups.py`), each job kind, and the contract every kind follows. It also covers how a statistic is composed (`src/pixano/statistics/`), since the statistics job computes it.

Other specs cover the rest. What the rows of a dataset hold, and the values `review_status` takes, belong to [`data-model.md`](./data-model.md) (`DATA`). What a person's edit or review does to a model's row, the explorer, the overview and the statistics routes belong to the REST API spec (`API`); until it is written, `docs/specs/backend-processing.md` still carries them ([During the move](./README.md#during-the-move)). The Jobs panel and the other screens belong to the legacy app spec (`UI`). How a model server serves a model belongs to the inference spec (`INF`). The import engine belongs to the import and export spec (`IO`), and so do when and how an import asks for its follow-ups, from the command line or the API, with the settings that decide it; this spec takes them from the moment they are fitted to the dataset the import wrote.

This spec obeys every rule of [`architecture.md`](./architecture.md) ([ARCH-1](./architecture.md#between-the-specs)). Several of its target rules are about this part of Pixano: PostgreSQL owned by `pixano-api` (ARCH-5, ARCH-6), versioned migrations (ARCH-7), a pool of connections (ARCH-10), write leases with fencing tokens (ARCH-14, ARCH-27), every long operation as a job (ARCH-23), a worker that gets its work from the API (ARCH-24), kinds found as plug-ins (ARCH-25), a registry of live workers (ARCH-26), fair sharing and a cap per model (ARCH-28), media in Lance and never as base64 in JSON (ARCH-12, ARCH-21), health routes and graceful stops (ARCH-55, ARCH-58), providers stored in the control plane (ARCH-29). Targets of [`data-model.md`](./data-model.md) are about it too: run-level provenance (DATA-16), videos stored as video (DATA-23), compaction and indexes as maintenance jobs (DATA-49). This spec decides nothing against them. Where a rule describes today's code in a way one of these targets will change, it says so with "until" and the target, and binds only until that target is reached; it also has its own target rules, each with its `_Today:_` line.

The words this spec uses:

- A **task** is the processing of one unit: a medium for embeddings, detection and segmentation, a frame of a video for tracking, a record for statistics. Each kind says what its task is.
- A **job** is one kind of processing run over one dataset. It is made of N tasks.
- A **chunk** is a batch of tasks: the unit a worker claims, runs and completes. Its **payload** says what it holds, in a form only its kind reads.
- The **final chunk** is the chunk that runs a kind's closing step, `finalize`, once every other chunk of its job is done. It holds no task.
- A **job kind**, or **kind**, is a plug-in of the worker: it brings its parameters, splits a job into chunks, processes a chunk and writes its result.
- The **engine** is what the worker does whatever the kind: claiming, leases, retries, recovery, progress, cancellation.
- **Planning** is the split of a job into chunks, by its kind, in the worker. **Preparing** is the kind's `prepare` step, run once per job after planning.
- A **lease** is the time during which one worker holds a chunk, or a job it plans. A lease that is not refreshed expires, and another worker can take the work.
- An **attempt** is one claim of a chunk. The count of attempts, `attempts`, is also the chunk's **fencing token**: a write about a chunk carries the attempt it was claimed at, and is refused once the chunk was claimed again.
- A failure is **transient** when the same chunk may pass later, **of an item** when one item of the chunk is at fault, and **fatal** otherwise.
- The **quarantine** is the list of the items a job could not process, each with its reason.
- A chunk's **outcome** says what each of its tasks became: **produced**, **skipped** (the computation does not apply to it, which is not a failure) or **quarantined**.
- A chunk's **weight** says how many times the worker's time limit it may run.
- A **follow-up** is a job an import queues once its data is in: the embeddings job, the statistics job.
- A **medium** is one view of a record: an image, a video, a point cloud, a text. Its **designation** is how a medium is named to the inference: a path, a URL, or its bytes.
- A **model's row** is a row whose `source_type` is `model`. A row is **reviewed** when a person accepted it ([DATA-14](./data-model.md)).
- **A person's work** is a row no model produced, a model's row a person accepted, or an entity that has a child entity.
- A **workflow** is a chain of jobs. Pixano has none yet: two jobs that depend on each other are run one after the other, by hand.

## Rules

### Between the worker and the app

**JOB-1.** `pixano-worker` MUST NOT import `pixano.api`, and `pixano` MUST NOT import `pixano_worker`. The worker MAY import the rest of the `pixano` package (its schemas, its dataset layer, its statistics). Until a registry of live workers exists ([ARCH-26](./architecture.md#execution-plane), target), the table `job_kinds` MUST be the only way the app learns what a worker runs.

_Why:_ the worker runs on a machine of its own, and needs the schemas and the dataset layer to write rows, not the web app. The weight of `pixano` is in the dependencies of LanceDB, which the worker needs anyway: a package shared apart would save 7 % of it.

**JOB-2.** The queue MUST be Pixano's own, on its own schema. A queue library that owns the worker's loop MUST NOT replace it.

_Why:_ a cap on the calls in flight per model, which [ARCH-28](./architecture.md#execution-plane) (target) gives the control plane, needs a claim that hands out a chunk only when a slot of its model is free. Procrastinate, evaluated, owns that loop, adds four tables to ours, and has no notion of a job made of N chunks.

### The queue and its schema

**JOB-3.** The queue, the state of each job and its events MUST live in PostgreSQL, in the schema `pixano_jobs` (`packages/pixano-worker/src/pixano_worker/sql/schema.sql`).

_Why:_ a worker that restarts needs no replay: the pending work is in the database. A schema of its own keeps the queue apart from what the control plane adds later ([ARCH-5](./architecture.md#control-plane), target). Today it holds six tables: `schema_version`, `job_kinds`, `jobs`, `job_chunks`, `job_items` and `job_events`.

**JOB-4.** While the worker owns the schema, until [ARCH-6](./architecture.md#control-plane) (target) gives it to `pixano-api`, the worker MUST install it at startup, from `schema.sql`, a file that takes no parameter and can be applied again, and the app MUST NOT create or alter anything in it. Where the schema does not exist, the app MUST answer that the queue does not exist yet.

_Why:_ one owner of the schema at a time.

**JOB-5.** While the worker installs the schema (JOB-4), a change to the DDL of `schema.sql` MUST bump `SCHEMA_VERSION` (`packages/pixano-worker/src/pixano_worker/schema.py`) in the same commit. A change to its comments alone MUST NOT.

_Why:_ `CREATE TABLE IF NOT EXISTS` creates a missing table and never alters an existing one. Without the version, a worker would run on tables that are no longer its own, and fail far from the cause.

**JOB-6.** Until versioned migrations exist ([ARCH-7](./architecture.md#control-plane), target), a worker MUST refuse to start when the database holds another version of the schema, and its message MUST give the `psql` command that drops the schema, then its Compose form.

_Why:_ the failure is loud and at startup. Today there is no migration engine: the queue holds nothing that cannot be rebuilt, so a changed schema is dropped and recreated empty.

**JOB-7.** While the worker installs the schema (JOB-4), two workers that install it at the same moment MUST both start: the one that meets a duplicate schema, table or index MUST try again, and find the schema installed.

_Why:_ `IF NOT EXISTS` is not atomic against a concurrent creator. PostgreSQL rolls the failed transaction back, so trying again is safe.

**JOB-8.** While the worker installs the schema (JOB-4), its PostgreSQL role MUST be allowed to create a schema in its database, at every start.

_Why:_ the worker applies `schema.sql` again at every start, and PostgreSQL checks the right to create before it tests `IF NOT EXISTS`: a role that loses the right after the installation makes the worker fail at its next start. It needs nothing else. [ARCH-6](./architecture.md#control-plane) (target) takes the worker's PostgreSQL credentials away.

**JOB-9.** The invariants of the queue MUST be constraints of the schema: a job carries an error only in state `error`, and a planning lease only in state `planning`; a cancellation has its own column, `cancel_requested_at`; a chunk is `running` exactly when it holds a lease, and carries an outcome exactly when it is `done`; only the final chunk is `waiting`, a job has at most one final chunk (a partial unique index on `job_id` where `final`), and a chunk has tasks exactly when it is not final; every payload, parameter set and error is a JSON object.

_Why:_ the two flaws of the SQLite store of imports, a cancellation written into the error and the liveness of a job told by a PID, become impossible by construction rather than avoided by convention. The index of the final chunk also lets its release, and the check that a job is finalizing, find it without a scan of the job's chunks.

**JOB-10.** Every timestamp of the queue MUST come from the clock of the database (`now()`), never from a worker.

_Why:_ a worker with a skewed clock must not be able to hold a lease too long, or take one too early.

**JOB-11.** A job's identifier MUST be a `uuid` that the database generates. The identifiers of chunks and events MUST be `bigint` identities.

_Why:_ neither the app nor the worker needs a library to make an identifier, and the database guarantees uniqueness. Increasing identifiers give the claim index locality and a first-in first-out order.

**JOB-12.** A chunk's payload MUST be opaque to the engine: a JSON object that only its kind reads. Its number of tasks MUST be a column, `task_count`, which the engine reads instead.

_Why:_ Pixano's tasks are not integers, and the most useful job is a selection, which has no range. An opaque payload is what lets every kind share one queue; progress is the engine's, which must never look inside a payload.

**JOB-13.** Claiming MUST be one statement over a partial index that holds only the pending chunks, with `FOR UPDATE SKIP LOCKED`, and MUST NOT join `jobs`. The recovery of expired leases MUST be a statement of its own.

_Why:_ the index holds only the chunks still to claim, so it shrinks as the work advances, and `SKIP LOCKED` walks it forward. Folded into the claim, the recovery would make the partial index unusable. Today the index is `job_chunks_pending_idx`, keyed by `id`, and chunks are claimed in the order of their identifiers; a cap per model may need the model on the chunk and another key; [ARCH-28](./architecture.md#execution-plane) (target) shares the workers fairly.

### The worker process

**JOB-14.** Until the providers are stored in the control plane ([ARCH-29](./architecture.md#inference-plane), target) and the worker gets its work from `pixano-api` ([ARCH-6](./architecture.md#control-plane), [ARCH-24](./architecture.md#execution-plane), targets), the worker MUST read its whole configuration from the environment. A setting without a default MUST stop the worker at startup when it is empty, and no default MUST stand for the address of another component or for a shared data location: the database, the inference, the library, the media roots. The heartbeat file, local to the worker and its probe, has a default. The settings are listed in [The settings](#the-settings).

_Why:_ a default that is only right on one machine connects the worker to the wrong place without a word, and it fails three layers further ([ARCH-3](./architecture.md#topology-and-deployment)).

**JOB-15.** `PIXANO_WORKER_ID` MUST be unique among the live workers and stable across the restarts of one worker. Without it, a worker MUST name itself `host:pid`.

_Why:_ the identity is what lets a restarted worker take its own chunks back at once. Two live workers with one name would take each other's chunks for orphans.

**JOB-16.** At startup and when it stops, a worker MUST hand back the chunks still running under its identity, and set aside those that used up their attempts, as JOB-42 says.

_Why:_ their lease would free them after two minutes. The same cap keeps a chunk that kills its worker on every attempt from looping for ever.

**JOB-17.** The worker MUST run its loop on asyncio, and the code of the kinds in a pool of threads of its own. The contract of a kind MUST stay synchronous.

_Why:_ LanceDB blocks whatever we do. The loop keeps for itself what gains from being asynchronous: the database, the delays and the leases.

**JOB-18.** A worker MUST NOT claim more chunks than it has free slots (`PIXANO_WORKER_CONCURRENCY`).

_Why:_ a claimed chunk's lease is already running. Claimed to wait for a slot, it could expire before it starts.

**JOB-19.** A running chunk's lease (`LEASE_TTL`) MUST be refreshed several times before it expires (`LEASE_REFRESH_INTERVAL`). A refresh that meets a database outage MUST be logged and tried again at the next interval, and MUST NOT count as the chunk's failure.

_Why:_ one slow query must not lose a lease, and a computation that succeeded must not be filed as fatal. If the database stays down past the lease, the lease expires and the fencing token refuses the result. A restart of PostgreSQL loses the lease today even when the database comes back within it (JOB-20, target). The lease is derived from the window of the Docker probe (four times 30 s); [ARCH-26](./architecture.md#execution-plane) and [ARCH-27](./architecture.md#execution-plane) (targets) bring heartbeats and fencing from the control plane.

**JOB-20 (target).** After a database outage, a running chunk MUST refresh its lease, record its progress and finish on a working connection, not on the one the outage broke.

_Why:_ a restart of PostgreSQL that lasts seconds must not cost every running chunk its work: a tracking chunk is a whole video.

_Today:_ a chunk holds one connection of the pool for its whole run, and refreshes its lease on it (`_run_pooled` and `_chunk_kept_alive`, `packages/pixano-worker/src/pixano_worker/runner.py`). A connection the outage broke is never replaced: the lease expires even when the database comes back, finishing the chunk fails, and the chunk is computed again.

**JOB-21.** A worker MUST recover the expired leases at most `RECLAIM_INTERVAL_S` after its previous pass, once its turn's planning is over, even when all its slots are full.

_Why:_ a full worker that waited for one of its chunks to end left a dead worker's chunks waiting with it.

**JOB-22.** The heartbeat MUST be a task of its own that touches a file (`PIXANO_WORKER_HEARTBEAT`) several times within the age past which the probe declares the worker dead (`MAX_HEARTBEAT_AGE_S`), and the probe (`python -m pixano_worker.healthcheck`) MUST fail when that file is older than that age.

_Why:_ a heartbeat once per loop turn made Docker declare a working worker dead during any long chunk. The heartbeat proves that the loop is not blocked; a chunk that hangs is the time limit's (JOB-66). [ARCH-55](./architecture.md#observability) (target) asks for liveness and readiness apart.

**JOB-23.** The pool of threads MUST count the threads still busy after the worker stopped waiting for them. When as many are stuck as chunks can be in flight, the pool MUST be renewed in place, its stuck threads abandoned, and the worker MUST go on.

_Why:_ a thread cannot be interrupted. Exiting the process relied on a restart policy whose count Docker never resets, so a worker stayed down for good at its third incident. The pool holds twice the concurrency plus one threads, so it still serves every slot when it reports itself saturated.

**JOB-24.** While the worker reaches PostgreSQL itself, until [ARCH-6](./architecture.md#control-plane) and [ARCH-24](./architecture.md#execution-plane) (targets), the worker MUST survive an outage of PostgreSQL: its loop waits with a capped backoff (`OUTAGE_BACKOFF_S`), its pool checks a connection before lending it and gives up a borrow after a bounded wait (`CONNECT_TIMEOUT_S`, in `__main__.py`), and a database error around a chunk leaves the chunk to its lease.

_Why:_ a restart of PostgreSQL killed the worker for good. A bounded borrow keeps a stop asked during an outage within the supervisor's grace.

**JOB-25.** An unexpected exception in a turn of the loop MUST be logged and survived, after a short pause (`UNEXPECTED_ERROR_PAUSE_S`), its trace logged once per series of repeats (`UNEXPECTED_ERROR_LOG_EVERY`). After a bounded number of failed turns in a row (`UNEXPECTED_ERROR_LIMIT`), the worker MUST stop as on a `SIGTERM`, and exit with code 1.

_Why:_ killing the worker made nothing more visible than its trace. A defect that does not pass in a minute, today's bound, will not pass in an hour, and a fresh process stands a better chance.

**JOB-26.** On `SIGTERM` or `SIGINT` received while its loop runs, between two plannings, the worker MUST stop claiming, give its chunks in flight `SHUTDOWN_GRACE_S`, hand back what still runs, and exit with code 0. A supervisor MUST give it more than that before it kills it; today the Compose file gives it `stop_grace_period`.

_Why:_ as the process 1 of its container without a handler, the worker ignored `SIGTERM` until Docker killed it, its chunks with it. [ARCH-58](./architecture.md#observability) (target) asks the same of every component.

**JOB-27.** A supervisor that runs the worker MUST restart it whenever it exits on its own, whatever its exit code; today the Compose file does (`restart: unless-stopped`). A worker that refuses a stale schema then restarts in a loop, with its message in every turn of the log, and that is accepted.

_Why:_ the decision was to refuse to start with a clear message, not to stay down for good. `on-failure:N` never resets its count, so the third incident of a long life left the worker down.

**JOB-28.** While the worker installs the schema (JOB-4), a worker MUST check the schema of the queue before it waits for the inference.

_Why:_ an incompatible schema is fatal, and the operator must learn it in two seconds, not after minutes of waiting for a server.

**JOB-29.** Every reason the worker writes, for a failed job, a failed chunk or a quarantined item, MUST be in English.

_Why:_ the interface shows these reasons as they are.

**JOB-30 (target).** `default_registry` MUST NOT register `fake`, `label`, nor any kind behind a demonstration switch.

_Why:_ a kind in the registry is offered in every Jobs form. A kind made for a demonstration computes nothing and misleads the person who runs it: Pixano must work with a user's own model and data, not with a stand-in (decided by the team on 2026-11-25).

_Today:_ `fake` and `label` are registered when `PIXANO_WORKER_DEMO_KINDS` is true, which is false by default (`packages/pixano-worker/src/pixano_worker/kinds/__init__.py`). No pull request removes them yet. Once they are removed, their rows stay in `job_kinds` wherever a worker declared them (JOB-143, [Known limits](#known-limits)).

**JOB-31.** The app MUST record a job request with no chunk, in state `planning`, and the worker MUST split it. The chunks, the job's total of tasks and its move to `pending` MUST be written in one transaction, with the state event.

_Why:_ splitting by video, by image or by selection is the kind's logic, and a kind's code runs in the worker only. One transaction means a job is never seen with half its work.

**JOB-32.** A job MUST be planned under a lease on the job (`planning_until`, `LEASE_TTL`), in the order the jobs were submitted, and until a registry of live workers exists ([ARCH-26](./architecture.md#execution-plane), target), by any worker. Recording or failing a plan MUST apply only to a job still in `planning`, and a cancellation MUST clear the planning lease.

_Why:_ a planner that dies lets its lease expire. Two planners that overlap cannot double the chunks, and a job cancelled during its split stays cancelled. The app stamps a job with the clock (`clock_timestamp()`), so the jobs queued in one transaction are planned in the order they were queued. Today a planning carries no fencing token: [ARCH-27](./architecture.md#execution-plane) (target) adds one.

**JOB-33.** Until a registry of live workers exists ([ARCH-26](./architecture.md#execution-plane), target), a worker that claims the planning of a job whose kind it does not run MUST fail the job, with the reason `unknown job kind`, and a worker that claims a chunk of such a job MUST fail the chunk, with the same reason.

_Why:_ saying it at once is better than leaving the job waiting with no explanation. Today a worker claims any job in `planning` and any pending chunk, whatever its kind, so in a fleet whose workers run different kinds this fails a job another live worker could run ([Known limits](#known-limits)). Restricting the claim to the kinds a worker runs would leave waiting, without a word, a job no live worker runs: ARCH-26 gives a piece of work only to a live worker that can do it, and settles both.

**JOB-34.** Planning MUST run the kind's `plan` first, then its `prepare`, and only when `plan` produced work. For a job over an existing dataset, planning MUST read the dataset opened again outside the worker's cache. A plan that raises, a plan with no chunk and chunks the schema refuses MUST fail the job with their reason, and the worker MUST go on.

_Why:_ everything that can refuse a job refuses it before `prepare` destroys anything. A dataset recreated under the worker is seen as it is now. A refused plan used to kill the worker and leave the job in planning.

**JOB-35.** A planning that meets a busy dataset (`DatasetBusyError`, or its subclass `DatasetReplacedError`) MUST leave the job in `planning`, with no error and no event, and cut its lease to a short delay (`PLANNING_RETRY_DELAY`), so that any worker plans it again. Nothing MUST bound these postponements.

_Why:_ someone else writing the dataset, a person's save, an import, another worker, says nothing about the job. Failed instead, the job made the person submit it again. `prepare` is idempotent, so planning again is safe. A job submitted during a long import waits in `planning` until the import ends.

**JOB-36.** A planning MUST wait for this worker's write lock of its dataset at most `PLANNING_WRITE_LOCK_WAIT_S`, then be postponed as JOB-35 says.

_Why:_ the loop waits for a planning within its turn, with no claim meanwhile, so the wait is short. Without a bound, a write that hung would stop every later planning of that dataset for good, with nothing to report it.

**JOB-37.** A planning, `plan` and `prepare` together, MUST be given at most `PLANNING_TIMEOUT_S`. Past it, the job MUST fail with `planning exceeded its time limit`, and a `prepare` that had not started MUST never start. A timeout the planning meets inside itself, a socket's, MUST be its own failure, not this limit.

_Why:_ a ceiling far above the work, so that only a planning stuck in its reads or in `prepare` reaches it and gives the loop's turn back. Planned again, it would hold the turn for the whole limit each time. `prepare` is checked against the limit under the write lock.

**JOB-38.** A kind that runs a model MUST ask the inference, in `plan`, whether it serves the model for the kind's capability (`InferenceServer.require_served`, `GET /v1/models`). A model it does not list MUST fail the job, the models it serves named. So MUST an answer of 401, 403, 404 or 405, and an answer the worker cannot read. A server that cannot be reached, or that answers anything else, MUST NOT fail the job.

_Why:_ without the check, such a job passed planning, `prepare` cleared what it was to replace, and every chunk failed on the same answer. A server that restarts is not a refusal: the chunks wait for it. Today the embeddings, detection, segmentation and tracking kinds all ask.

### Chunks and their failures

**JOB-39.** A chunk's failure MUST fall in one of three families. Transient (`TransientError`): the chunk goes back to the queue after a delay that doubles at each attempt up to a ceiling (`RETRY_BASE_DELAY`, `RETRY_MAX_DELAY`), and is set aside in `error` once it used up its attempts (`MAX_ATTEMPTS`). Of an item: the chunk finishes, and the item goes to the quarantine with its reason. Fatal, any other exception: the chunk fails. Its job's other chunks still run, and the job settles in `error` once none is pending or running (JOB-56, JOB-63).

_Why:_ handed straight back, a chunk would burn its attempts against an inference that is still restarting. With today's values, five attempts from 15 s leave about four minutes for it to come back, a restart with a model reload. A failed job is not a dead end: it can be run again (JOB-51).

**JOB-40.** Every statement by which the worker that claimed a chunk changes it (finishing it, failing it, cancelling it, handing it back, refreshing its lease, recording its progress) MUST carry the attempt the chunk was claimed at, and apply only while the chunk still holds it. A result whose attempt no longer matches MUST be dropped.

_Why:_ `attempts` is the fencing token: a worker whose lease expired must not overwrite, in the queue, the result of the worker that took the chunk over. It does not fence the chunk's write into the dataset, which comes before the chunk is finished: two attempts may both write, which JOB-82 makes harmless. [ARCH-14](./architecture.md#data-plane) and [ARCH-27](./architecture.md#execution-plane) (targets) fence that write. The recovery statements (JOB-16, JOB-21, JOB-42) carry no attempt: they act on chunks whose lease expired or whose worker restarted.

**JOB-41.** A chunk MUST also be handed back as transient when it outlasts its time limit (JOB-66), and when its write cannot take its dataset's lock in time (JOB-90, JOB-91).

_Why:_ none of these says anything about the chunk's work, which passes once the circumstance is over.

**JOB-42.** Both ways of recovering a chunk, from an expired lease and by a worker that takes its own chunks back, MUST count against the same attempts. A chunk that used them up MUST be set aside with the reason `abandoned after its attempts`, and its job settled.

_Why:_ a job whose last chunk was abandoned stayed `running` for ever, and a chunk that crashed its worker looped for good once restarts were automatic.

**JOB-43.** The recovery pass MUST also settle every job in flight none of whose chunks is pending or running (`settle_stranded`), releasing its final chunk when its work is done.

_Why:_ a worker that died between a chunk's result and the settlement that follows leaves such a job, and so does a retry with nothing to reopen. Nothing else would settle it.

**JOB-44.** A kind MUST blame an item only on an answer of the inference, never on its silence (`classify`, `packages/pixano-worker/src/pixano_worker/kinds/inference.py`). A transport error, the client's status 0, and an answer of 408, 429, 502, 503 or 504 MUST make the chunk transient. An answer of 401, 403, 404 or 405, or one the worker cannot read (`invalid_response`), MUST fail the chunk. Any other refusal MUST be the item's.

_Why:_ a server that refused a request said something about its content; one that did not answer said nothing. During a restart of the inference, a version that did not know status 0 sent seven healthy images to the quarantine.

**JOB-45.** When the inference refuses every medium of a chunk of still media, the kind MUST ask the server whether it is at fault, through `blame_the_server_or_the_media`. A 16 × 16 image the worker makes is sent as bytes: refused, the chunk is transient. Accepted, the first refused medium designated by path whose file this worker can read MUST be resent as the bytes of that file. Accepted then, the chunk is transient, and its reason names `PIXANO_INFERENCE_MEDIA_ROOT` on the worker and `PIXANO_INFERENCE_MEDIA_ROOTS` on the inference. Refused, the media go to the quarantine. A silence is transient, and an error no medium causes fails the chunk. When this worker can read none of the files, the media go to the quarantine.

_Why:_ a threshold on the number of refused media made the decision depend on the size of the batch, and the last chunk of a dataset often holds one image. A server that cannot read the storage it was told to mount refuses every path through no fault of the media; without the second call, hundreds of sound images would go to the quarantine.

**JOB-46 (target).** Before it sends a video to the quarantine because the inference refused it, the tracking kind MUST ask the server whether it is at fault, as JOB-45 does for still media, with a witness of its own.

_Why:_ an inference that cannot read the storage it was told to mount refuses every frame designated by path through no fault of the video: every video of the dataset would go to the quarantine, without the diagnostic of the mount the other kinds give.

_Today:_ a refused window raises `_VideoRefused` (`_call`, `packages/pixano-worker/src/pixano_worker/kinds/tracking.py`), and `process` quarantines the video as refused by the inference server, without asking the server.

**JOB-47 (target).** Each kind of media designation MUST bring its own refusal diagnostic, beside its designation: what to check when the inference refuses it, and whether the chunk is worth retrying. A new source of media then MUST add its case without changing `blame_the_server_or_the_media`.

_Why:_ the inference may only fail to reach a URL's source, a host missing from its allowlist or a presigned URL expired, and the media are not at fault.

_Today:_ only a path has one (`MediaResolver.path_refusal_diagnostic`). A medium designated by URL that the inference refuses with the rest of its chunk goes to the quarantine, and is not resent as bytes: the bytes this worker could send say nothing of whether the inference reaches the URL's source. Whether such a medium goes to the quarantine or its chunk is retried is open ([Open questions](#open-questions)).

**JOB-48.** A task the computation does not apply to MUST be counted as skipped, not quarantined. A chunk's outcome, produced plus skipped plus quarantined, MUST equal its `task_count`, and a chunk whose outcome does not MUST fail.

_Why:_ otherwise a lidar dataset fills the quarantine with tens of thousands of rows that are not errors. An outcome that is quietly wrong falsifies everything shown about the job.

**JOB-49.** The quarantine MUST hold one row per job and item (`job_items`), replaced when its chunk is replayed. A medium MUST be quarantined under its own identifier, its record in the detail.

_Why:_ the quarantine says what the last attempt found, not the history of every attempt. The panel shows the record.

**JOB-50.** A job's outcome MUST be summed when it is read, from its chunks and its quarantine, and MUST NOT be kept as counters on the job. `done_tasks` MUST be the one counter kept on the job, written in the transaction that finishes the chunk it counts.

_Why:_ a counter can drift from what it sums. `done_tasks` spares a sum over the chunks at every progress event, and a test compares it with that sum under concurrency.

**JOB-51.** `POST /jobs/{id}/retry` MUST run again a job in `error` or `cancelled`. Its chunks in error or cancelled go back to `pending`, with no delay, their attempts counted again from `attempts_floor` while `attempts` never goes down. Its error and its cancellation are cleared, and it goes back to `pending`, or to `planning` when it never got a chunk, with its state event in the same transaction. Its completed chunks keep their results. A job in any other state MUST be answered 409.

_Why:_ a failed job is not a dead end. `attempts` is the fencing token, so it must only grow: the floor says where the count starts again.

**JOB-52.** A failed job MUST say why: its own error when its planning failed, else the error of its first failed chunk, without the stack trace.

_Why:_ a job that read `error` and nothing else left the reason in the worker's log only. A stack trace is for that log, not for a browser.

### The final chunk

**JOB-53.** A kind that overrides `finalize` MUST get a final chunk, recorded at planning with the others: last in rank, with no task, in state `waiting`, which no claim reads.

_Why:_ some work makes sense only once every chunk is done, and the last chunk to finish does not know it is the last. As a chunk, the closing step inherits the claim, the lease, the attempts, the time limit, the delay, the cancellation and the retry, rather than a second copy of each.

**JOB-54.** Whoever settles a job MUST first lock the job's row (`FOR NO KEY UPDATE`), then release its final chunk when no other chunk of the job is left undone and the job is neither cancelled nor finished. The final chunk then becomes `pending`, a state event `{"state": …, "finalizing": true}` is written, and the job MUST NOT be settled yet.

_Why:_ without the lock, the last two chunks of a job finishing together could settle it `done` without its closing step, which then waited for good. `NO KEY UPDATE` does not conflict with the key share that recording a quarantined item takes through its foreign key, which deadlocked two chunks of one job.

**JOB-55.** The final chunk MUST run `finalize` in a thread, under this worker's write lock of the dataset, on the dataset opened again outside the cache. A `DatasetBusyError` MUST hand it back as transient.

_Why:_ it must see what every worker wrote. Its job's chunks are all done, and they must not be lost for a person's save.

**JOB-56.** The final chunk MUST NOT run after a failed chunk or a cancellation: such a job settles in `error` or `cancelled`, its final chunk still waiting, and a retry that brings the failed chunks through runs it then. A cancellation after the release MUST take the final chunk out of the queue with the other pending chunks. A cancellation that arrives while it runs lets it finish, and the job reads `cancelled`.

_Why:_ a closing step over half a result would describe the wrong dataset. Nothing is interrupted in the middle of a chunk.

**JOB-57.** The final chunk MUST count no task: the job's total, its progress and its outcome are those of its work. While the final chunk of a job in `pending` or `running` is queued or running, the job's `finalizing` MUST be true. Every state event that announces a job finalizing, the release's, the retry's that reopened the closing step alone, and that job's start, MUST carry `"finalizing": true`; what the cancellation's carries while the final chunk runs is JOB-58's (target). Any other state event of the job carries none, which clears it.

_Why:_ an interface then shows that a full bar is not stuck, from the events alone.

**JOB-58 (target).** The state event of a cancellation that arrives while a job's final chunk runs MUST carry `"finalizing": true`.

_Why:_ the final chunk goes on to its end (JOB-56), and the job is still finalizing until it settles.

_Today:_ the event carries the job's state and `cancel_requested` only (`cancel`, `src/pixano/api/jobs/enqueue.py`), so it clears `finalizing` in every open panel while the final chunk still runs.

### Cancellation

**JOB-59.** `POST /jobs/{id}/cancel` MUST record the request in `cancel_requested_at`, move the job's pending chunks to `cancelled`, and settle the job at once when none of its chunks runs (giving back its planning lease). The call that records the request MUST write a state event in the same transaction, with the job's state after it and `cancel_requested: true`; when a later call settles the job, JOB-60 (target) says what it writes.

_Why:_ it is the one state change the app makes itself. Without the event, every open panel but the one that clicked kept the job running. Moving the pending chunks is what keeps the claim from joining `jobs`.

**JOB-60 (target).** A cancellation that settles a job MUST write the job's state event, also when the request was already recorded.

_Why:_ a settled job without its event stays "cancelling" in every open panel, and no process of the app drops its cached dataset (JOB-73).

_Today:_ `cancel` (`src/pixano/api/jobs/enqueue.py`) writes the event only when it records the request. A second `POST /jobs/{id}/cancel`, after a recovery put a chunk back to `pending`, settles the job `cancelled` without an event.

**JOB-61.** A worker MUST check a job's cancellation before it runs one of its chunks, and every `PROGRESS_INTERVAL_S` while the chunk runs. A chunk that stops at the cancellation (JOB-150) MUST write nothing, and leave the queue as `cancelled`.

_Why:_ a cancellation of a long job is heard within seconds. Nothing a chunk stopped mid-way computed is kept: the chunk stays the atomic unit. Today only the tracking kind, and the demonstration kind `fake`, check while they run: the chunks of the other kinds run to their end, write, and are recorded `done`, since finishing a chunk does not look at the cancellation.

**JOB-62.** A chunk the worker stops waiting for, past its time limit, after its lease went to another worker, or because the worker stops, MUST be told to stop the way a cancelled chunk is (`ChunkProgress.cancel`). Only the chunk of a cancelled job MUST be marked `cancelled`; the others belong to whoever takes them back.

_Why:_ a thread cannot be interrupted. Told to stop, it ends at its next step instead of running on beside the attempt that took it over.

**JOB-63.** At settlement, a cancellation MUST win over an error: a job with a cancellation request settles `cancelled`.

_Why:_ a job that was stopped is not a job that failed.

### Progress, weight and time limit

**JOB-64.** A running chunk's progress MUST be recorded in `job_chunks.progress` every `PROGRESS_INTERVAL_S`, fenced as a result is. A job's progress MUST be its `done_tasks` plus the progress of its running chunks, summed under a lock of the job's row, and the app's job listing MUST sum it the same way. A chunk claimed again MUST start again from zero, and its job's progress MUST be announced at once.

_Why:_ a chunk that ran for minutes said nothing until it ended. The lock keeps a chunk that finishes meanwhile from leaving an older sum after a newer one. A panel that reloads its list mid-chunk shows its bar where the events left it.

**JOB-65.** A chunk's time limit MUST follow its work, through a weight its kind declares for the chunk at planning. The weight MUST default to one.

_Why:_ one limit for every chunk would either send back a long chunk the inference would still have answered, or leave a hung short one in its slot. How a weight becomes a limit is open ([Open questions](#open-questions)): today a kind weighs a chunk in the long calls it makes one after the other, the worker gives it its weight times `PIXANO_WORKER_CHUNK_TIMEOUT_S`, and only the tracking kind weighs its chunks.

**JOB-66.** A chunk past its time limit MUST be handed back as transient. Its thread MUST NOT be awaited any more: if it ever completes, the fencing token refuses its result.

_Why:_ a call that never returns must not hold a slot for ever. The write is idempotent, so a late write doubles nothing.

**JOB-67 (target).** Only the worker's own time limit MUST be reported as `time limit exceeded`. A `TimeoutError` the kind's code raises MUST be handled as the failure it is (JOB-39), as in planning (JOB-37).

_Why:_ a socket's timeout inside a kind says nothing about the chunk's time limit, and reported as it, it hides its cause.

_Today:_ `_execute` (`packages/pixano-worker/src/pixano_worker/runner.py`) catches any `TimeoutError`, of which the limit's `TimeLimitExceeded` is a subclass (`threads.py`), and hands the chunk back as transient with `time limit exceeded`.

**JOB-68.** A job MUST read `running` as soon as its first chunk is claimed. A second statement, run once the claimed chunks are started, MUST move their jobs from `pending` to `running` under each row's lock, in the order of their identifiers, with the state event in the same transaction. The first finished chunk MUST make the same move when that statement was missed.

_Why:_ a first chunk of five minutes showed `pending` for five minutes. The claim itself must not join `jobs` (JOB-13).

### Events and the stream

**JOB-69.** A state event MUST be written by the transaction that changes the state: the `running` event by the transaction that moves the job to running (JOB-68), each progress event under a lock of the job's row (JOB-64), the terminal event by the settling transaction. A progress event MUST carry absolute counters, never increments.

_Why:_ identifiers are handed out before commit, so events from two connections can become visible out of order. Absolute counters survive that; a state event has no later event to repair it.

**JOB-70.** Inserting an event and ringing its notification MUST be one statement, on the channel `pixano_jobs_events`, and the notification MUST carry identifiers only: `job_id`, `event_id` and `type`.

_Why:_ PostgreSQL delivers a `NOTIFY` at commit, so nothing is announced before it can be read. Its payload is capped at 8 kB, and a reader reads the row anyway ([ARCH-9](./architecture.md#control-plane)).

**JOB-71.** Each process of the app MUST listen with one connection, read the announced events with another, and hand them to its open streams. A stream whose bounded queue fills MUST be closed, so that its client reconnects and catches up.

_Why:_ a connection per open tab does not hold. A slow subscriber must not delay the others, and kept open, it would miss events without a word.

**JOB-72.** A stream MUST drop a duplicate by its identifier, never by order, within a window of `CATCH_UP_SLACK` identifiers. The stream of one job MUST resume from `Last-Event-ID`, reading back that many identifiers before it, so a resumed stream may send again events its client already received, which the client MUST drop by identifier. The stream of all jobs MUST have no catch-up.

_Why:_ a filter on "greater than the last" threw away for good an event that committed late. The stream of all jobs serves a list, which reloads itself when its stream reconnects.

**JOB-73.** For every terminal event its listener receives, each process of the app MUST drop its cached copy of the job's dataset, whether or not a stream is open.

_Why:_ the worker writes tables, an embeddings table above all, that a dataset opened before the job never sees: a search reported embeddings absent until a restart. A listener that reconnects does not catch up the events it missed, so that process keeps its copy until another job of the dataset ends or it restarts; [ARCH-20](./architecture.md#media-cache-and-the-way-to-the-inference) (target) brings every stale cache to every replica.

### The jobs routes

**JOB-74.** The routes listed in [The routes](#the-routes), other than the two streams, MUST answer 503 when no queue is configured (`PIXANO_DATABASE_URL` unset), when the queue cannot be reached as the route connects, and when the worker has not installed it yet. The 503 for a queue unset or not installed MUST name what to configure or start; the one for a queue that cannot be reached is JOB-76's (target). A stream route MUST answer 503 when no queue is configured.

_Why:_ it is a state of the deployment, not a client's error or a bug. A stream checks only its configuration before its headers are sent (JOB-77, target). A database that fails after the route connected is answered 500 ([Known limits](#known-limits)). [ARCH-2](./architecture.md#topology-and-deployment) (target) removes the mode without PostgreSQL.

**JOB-75.** A job identifier that is not a `uuid` MUST be answered 404 on every route, the event stream included, before the stream opens. A route other than the streams MUST answer an unavailable queue (JOB-74) first; a stream route MUST check the identifier first.

_Why:_ the schema types it as `uuid`: any other string made the query fail, a 500, or a stream that broke after its headers. A route other than the streams connects before it reads the job; a stream checks what it can before its headers.

**JOB-76 (target).** A 503 for a queue that cannot be reached MUST name what to configure or start, and MUST NOT carry the database's own message, which goes to the log.

_Why:_ anybody who calls `GET /jobs/kinds` would read the database's host, its user, and with a mistyped URL its password; the message names nothing to configure either. JOB-141 already keeps it from clients.

_Today:_ connecting to the queue puts psycopg's message into the error (`src/pixano/api/jobs/enqueue.py`), and the routes answer it as the 503's detail (`src/pixano/api/routers/jobs.py`).

**JOB-77 (target).** A stream route MUST answer 503 before it sends its headers when the queue cannot be reached or is not installed.

_Why:_ as JOB-74 says for the other routes, it is a state of the deployment, and a 200 that breaks tells the client nothing.

_Today:_ a stream route checks only that a queue is configured. When the queue cannot be reached or is not installed, `GET /jobs/{id}/events` answers 200 and then breaks while it reads the job's past events. `GET /jobs/events` answers 200 and sends only keepalives. When the queue cannot be reached, its listener tries again meanwhile; when it is not installed, the listener connects, since `LISTEN` needs no table, and no event comes until a worker installs the queue (`src/pixano/api/jobs/events.py`).

**JOB-78.** A submission of a kind that runs over an existing dataset MUST resolve its dataset first, a 404 when there is none. It MUST answer 422 to a kind no worker declared, and to parameters that do not validate against the JSON schema the kind declared. It MUST answer 202 with the job.

_Why:_ a job queued only to fail spares nobody. A misspelled parameter is refused at submission, not found at planning.

**JOB-79.** The app MUST check a submission against `job_kinds`, record it, list, read, cancel and run again jobs, and read the events and the quarantine. While the worker reaches PostgreSQL itself, until [ARCH-6](./architecture.md#control-plane) and [ARCH-24](./architecture.md#execution-plane) (targets) have `pixano-api` claim, lease and record progress on the worker's behalf, the app MUST NOT claim a chunk, hold a lease or record progress.

_Why:_ while the worker owns the database (JOB-4), the app is its second client, and the engine's work is the worker's. ARCH-24 moves that work behind routes of the API, whose shape is still open ([Open questions](#open-questions)). Its statements live in `src/pixano/api/jobs/queries.py`, and those of the event stream in `src/pixano/api/jobs/events.py`.

**JOB-80.** A route other than the two streams, and an import that queues its follow-ups, MUST wait a bounded time for the database of the queue to connect (`CONNECT_TIMEOUT_S`, `src/pixano/api/jobs/enqueue.py`), unless its URL sets its own `connect_timeout`.

_Why:_ psycopg's default, 130 s, held a server thread and the panel's "Checking…" that long when the database host dropped packets. The streams connect otherwise ([Known limits](#known-limits)). Today each request opens its own connection; [ARCH-10](./architecture.md#control-plane) (target) brings a pool.

### Writing into a dataset

**JOB-81.** A kind MUST reach a dataset only through the reader and the writer the engine gives it (`JobReader`, `JobWriter`). It MUST NOT open a dataset.

_Why:_ one door into LanceDB is where a cache, or a coordination of writers across workers, can be added without touching a kind.

**JOB-82.** A kind's write MUST be idempotent: a replayed chunk MUST leave the same rows, never duplicates.

_Why:_ results go to LanceDB and progress to PostgreSQL. Two stores share no transaction, so a chunk runs at least once, and may run twice.

**JOB-83.** A row that `JobWriter.replace` writes MUST take an identifier derived from the work, never from the job, as [DATA-15](./data-model.md) says: a digest of the kind, the model and the key, then the row's rank. A replace MUST delete exactly the pending rows a previous run of the same kind, model and key left beyond what it wrote, found by that prefix.

_Why:_ a rerun replaces the previous run's rows, and another model's rows add beside them. Found by prefix, the clean-up is exact however much an output shrinks.

**JOB-84.** A rerun MUST replace only the rows no person reviewed (`NOT_REVIEWED_STATUSES`, [DATA-14](./data-model.md)), as this worker's dataset holds them when `write` runs (JOB-86). A row a person accepted MUST keep its rank, and the new rows take the ranks left free. A previous row that a write's `covers` leaves out MUST keep its rank the same way.

_Why:_ an accepted row is a person's decision. `covers` is how a detection asked for dogs leaves the cars it found before.

**JOB-85.** When a write carries the entities its rows name, an entity MUST keep its rank when a person's work names it (`is_a_persons_work`), as this worker's dataset holds that work when `write` runs (JOB-86): a row of any table that names it by `entity_id`, or an entity whose `parent_id` it is. A model's row nobody reviewed MUST hold nothing, whatever its kind: a tracklet, a dynamic state, a mask. A row of the statistics tables MUST hold nothing either.

_Why:_ reassigning an entity a person worked on to whatever the model finds at the same rank would contradict them without a word. That an accepted row counts was decided on 2026-11-04: accepting is the person's choice to keep the row.

**JOB-86 (target).** A write MUST read the rows that protect a person's work after refreshing its view of the tables, under the dataset's write lock, so that a review or a save made through the app since the worker's last write protects as well.

_Why:_ an acceptance is a person's decision, and it must not go back to pending, or vanish, because a worker read an older version of the table.

_Today:_ `JobWriter.replace` reads the previous rows, and decides which are frozen, through the table handles the worker caches (`packages/pixano-worker/src/pixano_worker/writer.py`). A cached handle stays on the table version it opened until this worker's next `Dataset.write_lock` (`src/pixano/datasets/dataset.py`). A row a person accepts between the worker's last write and this read is not frozen: the new pending row is written over its identifier, or it is deleted as stale. The window lasts seconds for detection, and a whole video for tracking, which writes at the video's end only (JOB-122).

**JOB-87.** When a write rewrites an entity at its rank, or sweeps it, every model's row nobody reviewed that names it, as this worker's dataset holds those rows when `write` runs (JOB-86), MUST be deleted first, whatever its kind or its model. `drop_pending` with entities MUST do the same.

_Why:_ left behind, such a row would name whatever the rank holds next, or an entity that is gone. Holding the entity, it would freeze its rank, and every rerun would write the same entities again at the next ranks. Deleted first, a crash never leaves a mask on what is now another entity.

**JOB-88.** `JobWriter.drop_pending` MUST delete only a model's rows (`source_type = 'model'`) written under the kind's name and not reviewed, whatever their model. It MUST run only from a `prepare`, on an explicit parameter. With entities, it MUST spare the entities a person's work names, and delete the entities before the rows.

_Why:_ "replace the previous proposals" means the pending ones, and a person's row carrying the kind's name stays. Entities first: a crash leaves rows naming nothing, which the next attempt finds again as pending.

**JOB-89.** Within a worker, the writes to one dataset MUST be serialised by one lock per dataset, held around a kind's whole `write`, its reads included, and around `prepare` and `finalize`. `process` MUST run outside it.

_Why:_ LanceDB is not made for concurrent writes on a table, and the dataset's own lock never waits: two writes of one worker would fail one of them. A kind reads, decides and writes inside `write`, so the reads belong to the same serialisation. Across processes nothing serialises writes today; [ARCH-14](./architecture.md#data-plane) (target) gives every writer a lease.

**JOB-90.** Every wait for that lock MUST be bounded: a planning waits `PLANNING_WRITE_LOCK_WAIT_S` (JOB-36), and a chunk waits `CHUNK_WRITE_LOCK_WAIT_S`, then is handed back as transient.

_Why:_ the lock lives at module level, so renewing the pool cannot release it, and a write that never returns holds it until the process ends. A chunk's wait outlasts the writes queued ahead and stays far below a chunk's time limit.

**JOB-91.** On a local dataset, a chunk's write that another process's write refuses (`DatasetBusyError`) MUST be tried again at short intervals (`CHUNK_DATASET_BUSY_RETRY_S`) for a bounded time (`CHUNK_DATASET_BUSY_WAIT_S`), then the chunk handed back as transient. A write through a dataset recreated underneath (`DatasetReplacedError`) MUST fail the chunk.

_Why:_ the result is in memory, and its inference is the costly part, while a person's save lasts a fraction of a second. Past that wait, something longer holds the dataset, an import, and the chunk waits its turn in the queue rather than in a slot. On S3 nothing refuses a write ([Known limits](#known-limits)); [ARCH-14](./architecture.md#data-plane) and [DATA-39](./data-model.md) (targets) give every writer a lease.

**JOB-92.** Until compaction is a maintenance job ([DATA-49](./data-model.md), target), the writer MUST compact a table after every `COMPACT_EVERY_WRITES` writes to it in a dataset, counted within a worker since it started, in the chunk that triggers it and under the write lock, and clean the versions older than `KEEP_OLD_VERSIONS_FOR`. A compaction that fails MUST be logged, and MUST NOT fail the chunk.

_Why:_ each write makes a Lance version, 6 250 of them for a job of 50 000 images, and a fragmented table slows every read. The delay protects a reader that holds an older version. DATA-49 takes the compaction out of the chunks' write lock.

**JOB-93.** A worker MUST keep a bounded number of datasets open, and, on a local dataset, open again a cached dataset whose `info.json`, `embeddings.json` or folder another process changed (`Dataset.is_stale`). Planning and the final chunk MUST open the dataset again outside the cache. A dataset whose files cannot be examined MUST be served as it was opened.

_Why:_ a chunk must not read a space another worker created, or write into one it deleted, from what this worker read before. Opening again a dataset that cannot be examined would fail the same way. A change to a table's rows alone does not make a dataset stale (JOB-86), and on S3 nothing does ([Known limits](#known-limits)).

**JOB-94.** The writer MUST answer a table the dataset already declares from the dataset's metadata (`JobWriter.ensure_table`), and statistics columns it already holds from the table's own schema (`JobWriter.ensure_statistics`), both without the dataset's lock. Only adding a table or a column MUST take the lock.

_Why:_ that lock never waits. Taken by every job for nothing, it refused the job whenever someone else was writing the dataset.

**JOB-95.** Until runs are recorded once ([DATA-16](./data-model.md), target), every row written with `writer.provenance()` MUST carry the `source_type` its kind declares, the kind's name as `source_name`, and in `source_metadata` a JSON object: `job_id`, `kind`, `model` and `model_version` when the kind runs a model, and `params`, the job's parameters minus the engine's. A kind whose `source_type` is `model` MUST get `review_status = "pending"` from the writer, and a kind MUST NOT set `review_status` itself.

_Why:_ the jobs are cleaned by truncating their tables, so the job identifier is kept as an opaque label of the run, and the rest says how the row was made without any table to look up. A model's row arrives to be reviewed ([DATA-14](./data-model.md)). [DATA-16](./data-model.md) (target) records the run once and has rows name it.

**JOB-96.** A kind that runs no model MUST NOT declare `source_type = "model"`. `source_type` MUST take the vocabulary of the schemas: `model`, `human`, `ground_truth` or `other`.

_Why:_ what matters to a reviewer is whether a model made the row. A count measured by a rule is not a prediction, and `job` is refused at write time.

### Media

**JOB-97.** Until media reach the inference as [ARCH-21](./architecture.md#media-cache-and-the-way-to-the-inference) (target) says, and a dataset holds its media as [DATA-22](./data-model.md) (target) says, the worker MUST designate each medium for the inference in this order (`MediaResolver.resolve`): an `http://`, `https://` or `s3://` URI as it is; a path under `PIXANO_MEDIA_ROOT`, as the same path under `PIXANO_INFERENCE_MEDIA_ROOT`; otherwise the view's bytes, read from the dataset and sent as a data URI. It MUST say which it chose (`ResolvedMedia.designation`: `url`, `path` or `bytes`).

_Why:_ a path is preferred, and bytes are the fallback, since a view imported in `embed` mode, the default, has no path. What was chosen decides what can be checked when the inference refuses a medium (JOB-45). The bytes sent as base64 are today's fallback: ARCH-21 forbids base64 in a JSON body, and [ARCH-12](./architecture.md#data-plane) and DATA-22 (targets) keep media in Lance, admit only `https://` and `s3://` URIs, and translate no path.

**JOB-98.** A path MUST be normalised before it is compared to the media root, and only an absolute path under the root MUST be translated.

_Why:_ the comparison is lexical: `/medias/../etc/passwd` passed for a path under `/medias`.

**JOB-99.** The worker MUST read a medium's file itself only when its real path, links followed, is under the real path of its media root (`MediaResolver.local_path`).

_Why:_ checked on the text of the path, a link under the root to a file outside it was read, and resent to the inference.

**JOB-100.** A chunk MUST carry what designates its work, identifiers, never the data itself.

_Why:_ encoded images in payloads would swell the chunk table by the weight of the dataset.

### The embeddings kind

**JOB-101.** The embeddings kind MUST write one vector per medium, with its `view_id`, into the table of its model ([DATA-43](./data-model.md)). Its task MUST be a medium, of the types the job chose; it sends images only. Its chunk MUST name the media table, the media and the checkpoint planning read, and its media MUST be sent to the inference in one call; a batch the inference refuses MUST be split in two until the media refused on their own are isolated.

_Why:_ a nuScenes record holds six camera images and a lidar sweep: by record, a chunk held six images or none. By medium, a chunk's cost is its number of calls.

**JOB-102.** The embeddings kind's `chunk_size` MUST be both the unit of work and the size of the batch sent to the inference; a kind that needs the two apart MUST declare a `batch_size` of its own.

_Why:_ its default, 8 today, was measured on the CPU stack: bigger batches were slower, with the cost inside the inference call, and 8 is also the smallest unit a retry redoes. On a GPU the order will probably reverse, which is what the parameter is for.

**JOB-103.** An embedding's identifier MUST be a digest of the kind and its medium, without the model (`derive_id(kind, view_id)`), and an embedding row MUST carry no provenance. Vectors written one per record, under the identifiers of an earlier version, MUST stay until a job of their model runs with `replace_existing_embeddings`.

_Why:_ a table holds one model, so a rerun overwrites a medium's vector. The model and its checkpoint name the space a vector goes to.

**JOB-104.** The embeddings kind MUST refuse at planning a dataset whose `embeddings.json` it cannot read entirely. Another model's vectors MUST NOT refuse a job.

_Why:_ rewritten, the description would lose what this build left out, and the vectors it names. Each model has a table of its own.

**JOB-105.** A chunk MUST write its vectors under the checkpoint the inference serves right after the chunk's call, else under the one planning read, and never under one remembered from another job. Planning MUST read the checkpoint again, and forget it when the server cannot be asked. Planning MUST refuse a job when the server names no checkpoint and the dataset holds several checkpoints of the model. A chunk that cannot tell its checkpoint among several spaces MUST be handed back as transient, and one whose checkpoint matches several spaces recorded without theirs MUST fail. A chunk that cannot tell its checkpoint, on a dataset holding one space of the name, MUST write into that space and say so in the log.

_Why:_ the server does not say which weights answered a call, so the closest is to ask right after it. Weights deployed again during a job go to a space of their own. Nothing is placed by guess.

**JOB-106.** A chunk MUST find or create its model's space, and write its vectors, under one acquisition of the dataset's write lock, which reads the description again (`Dataset.upsert_record_embeddings`).

_Why:_ on a local dataset, a space another worker created meanwhile is found, not created twice; one it deleted is created again, never written into from what this worker read before. On S3 the lock does nothing ([Known limits](#known-limits)); [ARCH-14](./architecture.md#data-plane) (target) gives every writer a lease.

**JOB-107.** `replace_existing_embeddings` MUST empty, in `prepare`, the table of the job's model and checkpoint in place, keeping its space's identifier, its place and the default, the other models' tables kept. A job whose checkpoint is not told MUST empty only a space recorded without one, and MUST be refused rather than empty a space whose checkpoint is told.

_Why:_ accepted under conditions: the vectors are dropped once, under the planning lease, and the form asks for confirmation. A space of a told checkpoint may hold other weights' vectors.

**JOB-108.** Until index refreshes are maintenance jobs ([DATA-49](./data-model.md), target), the embeddings kind's `finalize` MUST index every space of the model's name (`writer.index_embeddings`): compact its table, build its `record_id` index, then the vector index the space declares when the table holds enough vectors ([DATA-44](./data-model.md)), each rebuilt whole. It MUST NOT take the dataset's own lock. A build that fails MUST hand the final chunk back as transient, once every space was tried.

_Why:_ an index is trained on the whole table, which no chunk sees, and would be trained again at every write. Building an index changes no row, so a person's save is never refused for it. A build fails mostly on a commit of another writer of the table, and passes later. The final chunk cannot tell which checkpoint of the name the job wrote. DATA-49 takes the build out of the chunks' write lock.

### The detection kind

**JOB-109.** The detection kind MUST write each box into `bboxes`, pending, in normalised `xywh`, with the model's score as `confidence`, brought within [0, 1], and the entity it names into `entities`, sharing the box's identifier. The class MUST go in the field `label_field_of` chooses, and an entity schema with no text field MUST gain `category`. Its key MUST be the image, with one call per image.

_Why:_ the shared identifier is how the writer keeps an entity with a frozen box and deletes it with a stale one. The class goes where the interface reads a class. The inference's detection endpoint takes one image.

**JOB-110.** Planning MUST refuse a dataset without a `bboxes` or an `entities` table, and one whose entities hold no text field and a `category` field of another type. An image whose size the dataset does not record MUST be measured from its header, and quarantined when it cannot be.

_Why:_ every write would fail on such a dataset, chunk after chunk. A dataset imported by URI records no size.

**JOB-111.** A detection job asked for `classes` MUST replace only the pending boxes of those classes, case aside; without classes, every pending box the same model wrote on the image. `replace_previous`, confirmed in the form, MUST delete at planning the kind's pending boxes, whatever their model, with their entities: every one of them for a job without classes.

_Why:_ asked for dogs, then for bicycles, a job keeps the dogs (decided 2026-10-20). Which boxes `replace_previous` deletes for a job asked for classes is open ([Open questions](#open-questions)): today, only those of the classes asked for.

**JOB-112.** A detection MUST NOT be written when its intersection over union with a box a person drew or accepted, of the same class, case aside, reaches `overlap_threshold` (0.5 by default), as this worker's dataset holds that box when `write` runs (JOB-86). A person's box without a class MUST stand for any class. A pending box whose entity carries a person's work MUST be protected like a person's box.

_Why:_ the person already said what is there. A rejected box is deleted, so nothing keeps the model from proposing it again, which was accepted with that decision.

### The segmentation kind

**JOB-113.** A segmentation MUST NOT write a mask whose intersection over union with a mask a person drew or accepted, on an entity of the same class, case aside, reaches `overlap_threshold` (0.5 by default), counted pixel by pixel when both masks are on one grid, and between their bounding boxes when the grids differ, as this worker's dataset holds that mask when `write` runs (JOB-86). A person's mask whose entity has no class MUST stand for any class.

_Why:_ the person already said what is there, as JOB-112 says of a box (the threshold decided 2026-10-20). The rest of how the kind writes its masks, and what else a person's mask protects, is provisional ([Open questions](#open-questions)).

**JOB-114.** Every mask MUST be checked (`packages/pixano-worker/src/pixano_worker/kinds/masks.py`) before pycocotools reads it. The kind MUST NOT invent a score for a mask.

_Why:_ pycocotools loops for ever, holding the GIL, on runs that do not fill their grid. A mask has no score column, and a placeholder would read as a score.

### The tracking kind

**JOB-115.** A tracking job MUST follow each entity it names (`objects: [{record_id, entity_id, frame_index}]`) from that frame, prompted by its box or mask there, whoever drew it. A job that names none MUST follow every entity a person annotated on a frame of a video, from the first frame where they did; a model's annotation MUST start no track unless a person accepted it. The model MUST be one the inference serves for `tracking` (the task `video_mask_generation`).

_Why:_ one kind for one entity and for a whole dataset (decided 2026-11-05). The generic form cannot build a list of entities, so a job submitted there names none.

**JOB-116.** A video MUST be one chunk, from the earliest keyframe of its entities to its end, and its tasks MUST be its frames after that keyframe. Until videos are stored as video ([DATA-23](./data-model.md), [ARCH-16](./architecture.md#data-plane), targets), the kind MUST read a video stored as frames: a view of a record whose frames are a sequence, told apart by their logical name ([DATA-2](./data-model.md)), an annotation naming its video by `view_id` and its frame by `frame_index`. A video with no frame after the keyframe MUST NOT be planned, and a job with no video left MUST be refused.

_Why:_ an entity's identity runs through the whole video, which chunks cut across would lose. A record filmed by several cameras holds as many videos.

**JOB-117.** A job that names no entity MUST look for its keyframes among a person's work only, filtered in the query, and read in one pass.

_Why:_ what models proposed, the masks of earlier tracks included, is not read at planning. A filter read by pages reads every matching row again for each page.

**JOB-118.** The frames MUST go to the inference by windows of `window` frames for one entity; a call that follows several entities takes as many times fewer frames, two at least. A window MUST start on the previous window's last frame, prompted with the mask the model gave there. An entity MUST be prompted on its keyframe by a person's mask there, else their box, else the model's. Tracking MUST go forward only. An entity with no mask on a window's last frame is lost, and leaves the video.

_Why:_ on the local stack's CPU, sixteen frames, today's default, keep a call between four and eight minutes, and each entity costs about as much as a frame. A box a person draws where the model drifted prompts the track, not the drifted mask. Forward only was decided on 2026-11-05.

**JOB-119.** By default, a failed tracking call MUST NOT be tried again at once (`max_retries` defaults to 0): its chunk goes back to the queue, after its delay. The client's limit on a call (`request_timeout_s`) MUST default to more than the inference's own limit on a tracking call.

_Why:_ a replica answers one call at a time, and goes on computing a call that timed out: a retry would wait behind it, and the window would be computed twice. The server's answer must arrive before the client gives up. Today's default, 1 860 s, is a minute above the local inference's limit; a job may ask for up to ten retries.

**JOB-120.** A video one of whose frames cannot be found, or that the inference refuses (JOB-46, target), MUST go to the quarantine whole, as one item named by its first frame, its record and its camera in the detail, its other frames skipped. A frame on which no entity got a mask MUST be skipped. A silence of the inference MUST be transient.

_Why:_ no entity can be carried across a missing frame.

**JOB-121.** A mask the model answers empty, unreadable, or not of its frame's height and width when the frame records them, MUST be set aside: its entity counts as lost on that frame, and gets no mask and no box there. The write MUST log how many were set aside.

_Why:_ a malformed mask must not be written, and a box drawn around it would be wrong.

**JOB-122.** Nothing MUST be written before a video's end. The rows MUST be keyed by kind, model, video and entity, the boxes and the tracklet with their table's slot added to the key, and replace those of an earlier attempt or run.

_Why:_ an interrupted video is tracked again from its start, and its rows must not double or mix. Each table numbers a key's rows from zero, and the interface finds an annotation by its identifier, whatever its table.

**JOB-123.** `output` MUST choose what the job proposes on each frame an entity is followed to: `masks`, the default, `boxes` or `both`, with one tracklet per entity and video spanning them. A box MUST be the bounding box of the model's mask on its frame, in normalised `xywh`, and carry no score: today the schema's mark for none, `confidence` -1; [DATA-13](./data-model.md) (target) makes it null. A job asked for boxes alone MUST NOT give the dataset a masks table. The rows MUST carry the video's first frame as `view_id`, the frame's `frame_id` and `frame_index`, and the tracklet's `tracklet_id`, with every model row's provenance, `output` included and the entities pointed at left out.

_Why:_ boxes were asked for on 2026-11-19, as a choice of the job, masks by default so that nothing changes without it. The choices of this rule and of the next two were made while implementing, and confirmed on 2026-11-24. SAM 2's video predictor answers masks and no score. The rows sit where the legacy workspace's interactive tracking puts its own.

**JOB-124.** A track from a later frame MUST replace only the model's rows after its keyframe, and on the keyframe when a person's annotation prompted it, and only in the tables of the output it was asked for. The tracklet MUST span every mask that names it and every box this kind wrote that names it, a person's box not counted, and go only when nothing names it any more.

_Why:_ a person who draws the box where the model drifted, and tracks again from there, keeps what the first track proposed before. A job must not delete proposals nobody asked it to replace.

**JOB-125.** `write` MUST read again what a person did, as this worker's dataset holds it when `write` runs (JOB-86): a frame on which the entity holds a mask a person drew or accepted gets no model mask, and one on which it holds such a box gets no model box, each table on its own. An entity deleted meanwhile MUST get nothing, and lose the model's masks and boxes, whatever the job was asked for. The keyframe's annotation MUST stay as it is.

_Why:_ `process` ran outside the write lock. Each table protects a person's work on its own so that a job asked for masks writes what it wrote before boxes existed. Nothing will track a deleted entity again to clean what the other output left.

**JOB-126.** A tracking chunk MUST report its progress after each window, in frames, hear a cancellation between two windows, and declare a weight that grows with its windows.

_Why:_ a video runs for minutes in one chunk, and its time limit must follow its work (JOB-65). Today its weight is its frames divided by the frames each call advances, rounded up, as JOB-65's open question leaves it.

### The statistics kind

**JOB-127.** A statistic MUST be composed from fixed choices only, never a formula or code (`pixano.statistics.definitions`): a level, one value per record or per entity; an element, an annotation kind by its `DatasetInfo` slot or, per record, its entities (`entity`); a measure, a count, or for boxes and masks their area in pixels or the share of their image they cover; an aggregation of several areas, mean, min, max or sum; and optional filters on an entity's attribute, on the annotation's origin, and on a model's review status.

_Why:_ statistics are no fixed list, and a person composes what fits the dataset. Fixed choices can be checked and named.

**JOB-128.** A combination that measures nothing meaningful MUST be refused: entities measured per entity, the area of anything but a box or a mask, an aggregation on a count or none on areas, an origin or a review status on entities, a review status of annotations no model made or of a kind no interface reviews. A review status MUST imply the model's origin.

_Why:_ a statistic that means nothing would fill a column all the same. The same statistic gets the same name whether its origin was given or implied.

**JOB-129.** A statistic's column name, unit and type MUST follow from its choices, within what [DATA-45](./data-model.md) allows a statistics column: lower-case ASCII letters, digits and underscores, a letter first (`COLUMN_NAME_PATTERN`), the unit in the name, each filter adding what it keeps, an attribute's text transliterated to ASCII; a name past 63 characters is cut and ends with a hash of the whole. A count MUST be a whole number with no unit, an area a decimal in px², a share a decimal with none. A label MUST take at most 120 characters, a description 1 000, an attribute value 512.

_Why:_ a dot would read as a nested field, and a leading underscore names the columns Lance adds. 63 characters is PostgreSQL's limit on an identifier, the strictest engine a column may meet.

**JOB-130.** Each measure's computation MUST have a version (`MEASURE_VERSIONS`). A computation that changes MUST take the next version, and its statistic a column of its own; a statistic composed at an older version MUST be neither computed nor offered any more.

_Why:_ new values must not be written over the old ones without a word.

**JOB-131.** The library's statistics MUST be kept in a LanceDB table, `statistic_definitions`, in the library's `.pixano` folder, one row per statistic with its choices as JSON. Within one process of the app, composing the same choices at the same version MUST answer the statistic stored, its name and label included, and a name another statistic took MUST end with a hash of its choices, then a number when that is taken too. A row that no longer reads as a statistic MUST be left out and logged once. Only the app MUST read and write this registry.

_Why:_ a name, once stored, is its column for good. A new choice must not change the table's columns. A rule added since must not keep the library from opening. The registry is guarded by a lock of one process: two replicas of the app can store the same name, which [ARCH-8](./architecture.md#control-plane) (target) rules out.

**JOB-132.** A statistics job MUST receive the definitions it computes in its parameters, a bounded number of them (`MAX_STATISTICS_PER_JOB`), each once, and compute them as they were composed. Each definition MUST agree with its own choices, its level, its type and its unit, or be refused (`StatisticDefinition._agrees_with_its_choices`). The worker MUST NOT open the registry. The kind's parameter schema MUST carry `x-pixano-own-form`.

_Why:_ a job replayed computes what it was submitted with, whatever the registry became. The generic form cannot build definitions: the app sends them itself. Anybody can send a job's parameters: a definition with another level would write into the other level's table, and one with another type would make a column the right values can never go to.

**JOB-133 (target).** A statistics job MUST refuse a definition whose name is neither the one its choices give nor that name suffixed as JOB-131 says.

_Why:_ anybody can send a job's parameters: a definition named as another column of the same type would write over that column's values, and over the definition the dataset records.

_Today:_ `_agrees_with_its_choices` (`src/pixano/statistics/definitions.py`) checks the level, the type and the unit, not the name, and the writer writes into the column the name gives (`write_statistics`, `packages/pixano-worker/src/pixano_worker/writer.py`).

**JOB-134.** The statistics kind MUST call no inference, and declare `source_type = "other"`. Planning MUST refuse, naming them, a statistic whose measure took another version since it was composed, one that measures a mask's area or share, and one that measures what the dataset does not hold or filters on an attribute its entities lack. Every chunk MUST refuse the first two again. A chunk MUST be a batch of at most 1 000 records.

_Why:_ a measure computed otherwise would land in the column of the previous computation. Masks' areas are not measured yet. A worker updated since the plan must refuse as well. A chunk's records are read in one query per table, and 1 000 is the most identifiers one query names.

**JOB-135.** The computation (`pixano.statistics.compute`) MUST give: a count as a whole number, 0 when nothing is kept; an aggregation of areas, no value when there is none, a sum of nothing kept 0. Per record, every annotation of the record counts, and the entities counted are those with no `parent_id`; per entity, the annotations that name it. An entity whose attribute does not hold the value a statistic filters on MUST get no value, not 0. A box MUST be measured against the view it is drawn on, its frame when it names one, without being cut at the view's edges; a box whose measure needs its view's size (an area of normalised coordinates, a share of pixel coordinates) and whose view has no known size, or whose area is not a finite number, MUST be left out.

_Why:_ a record without boxes has no mean box area. A statistic that filters on an attribute value does not apply to an entity without it.

**JOB-136.** The statistics job's `prepare` MUST add the tables and columns missing. Every chunk MUST write only its own columns, on rows whose identifier is the record's or the entity's, and, when the job computes a statistic per entity, delete the rows of the entities its records no longer hold. `finalize` MUST record in the dataset what the job computed (`writer.record_computed_statistics`). Statistics rows MUST carry no provenance.

_Why:_ the other statistics of a row keep their values, and a replay writes the same values over the same rows. The dataset says which job computed each column last.

**JOB-137.** The default statistics MUST be the four of `pixano.statistics.defaults`: per record, how many entities, boxes and masks it holds; per entity, the mean share of its image its boxes cover. They MUST be composed as any statistic.

_Why:_ they are what a dataset's overview counts and cannot read from a table as it is. A person composing the same choices gets the same column.

### Follow-ups after an import

**JOB-138.** An embeddings follow-up asked for explicitly with no model to name MUST queue nothing, the dataset's own models included, and MUST say so at once.

_Why:_ decided on 2026-11-10: a request with nothing to name is told at once, as before the dataset kept one table per model, rather than turned into jobs it did not name.

**JOB-139.** Fitted to the dataset the import wrote, the embeddings follow-up MUST become one job per model name: the model the import named, first, then every model the dataset holds. A model the deployment chose MUST stand in only for a dataset without embeddings. A dataset with no still image, or whose `embeddings.json` cannot be read entirely, MUST get no job, with the reason.

_Why:_ the media an import added are in none of the dataset's embeddings (decided 2026-11-06, the details on 2026-11-10). The embeddings job cannot compute only what is missing, so each job computes the whole dataset again, at a cost still open ([Open questions](#open-questions)). A held model the inference no longer serves is refused at its job's planning.

**JOB-140.** Fitted to the dataset the import wrote, the statistics follow-up MUST become the job of every default statistic the dataset holds rows to count for, each with the label the dataset or the library gave it. A dataset with nothing to count MUST get no job, told as not needed (`FollowUp.skipped`), not as a refusal.

_Why:_ nothing in a request tells whether the dataset will hold anything to count, and the records an import adds have no value of the default statistics. Today the job computes the whole dataset again, which stands for now and is to revisit ([Open questions](#open-questions)).

**JOB-141.** An import's follow-ups MUST be queued in one transaction, its statements and lock waits bounded (`QUEUE_STATEMENT_TIMEOUT_MS`). A database error MUST leave every follow-up saying that the queue could not be read, and the database's own message MUST go to the log only. One whose fitting fails MUST say so alone, and the others are queued.

_Why:_ queueing holds the import's runner meanwhile. A database error can name its host, its user, even a password in a mistyped URL.

### The job-kind contract

**JOB-142.** Adding a kind MUST NOT require changing the engine. Until the kinds are found as plug-ins ([ARCH-25](./architecture.md#execution-plane), target), a kind MUST be registered in `default_registry` (`packages/pixano-worker/src/pixano_worker/kinds/__init__.py`), and given an example in the contract suite (`packages/pixano-worker/tests/test_kind_contract.py`). The contract suite MUST fail a registered kind without one.

_Why:_ the proof that a kind is a plug-in is mechanical: one suite runs over every kind. A kind nobody knows how to exercise has escaped the contract. [ARCH-25](./architecture.md#execution-plane) (target) finds the kinds through entry points.

**JOB-143.** Until a registry of live workers exists ([ARCH-26](./architecture.md#execution-plane), target), each worker MUST declare its registry in `job_kinds` at startup, each kind with the JSON schema of its parameters, over the previous declaration of that kind. A declaration MUST NOT be withdrawn when its worker stops.

_Why:_ what the deployed code runs is the only truth the app can check a submission against. Today a job of a declared kind whose workers are all down is accepted and waits; [ARCH-26](./architecture.md#execution-plane) (target) brings a registry of live workers.

**JOB-144.** A kind's parameters MUST be a pydantic model that inherits `JobParams`, which forbids unknown fields.

_Why:_ it makes the published schema say `additionalProperties: false`, so a misspelled parameter is refused at submission instead of being ignored.

**JOB-145.** `plan` MUST give every chunk at least one task, and planning a job twice MUST describe the same work. `plan` MUST NOT rely on what `prepare` will do.

_Why:_ a chunk with no task takes a turn and advances nothing. A job planned again after an outage must not describe something else than what was partly done.

**JOB-146.** `prepare` MUST be idempotent, and MUST destroy nothing unless an explicit parameter asks for it. It MUST stay far below the planning's time limit (JOB-37) on the largest dataset it will meet, and MUST let a `DatasetBusyError` through.

_Why:_ a planner that dies after `prepare` lets its lease expire, and the next one does both again. A job with default parameters must never lose what the dataset holds. The runner postpones a busy planning; any other error fails the job.

**JOB-147.** `finalize` MUST be idempotent, MUST delete no row, and MUST read the dataset, never the chunks. It MAY rebuild what derives from the rows, as an index. It MUST raise `TransientError` for a failure of circumstance.

_Why:_ a worker that dies while finalizing lets the final chunk run again, maybe elsewhere. The chunks' payloads and results are gone, and other workers wrote part of them.

**JOB-148.** `process` MUST write nothing. `write` MUST write everything a chunk produces, through the writer, and read through the writer what it decides on.

_Why:_ they fail differently: an inference call can be retried, a write must never be half done. The reads inside `write` belong to the serialisation of the write (JOB-89).

**JOB-149.** A kind MUST report a failure by its family: raise `TransientError` for what outlasts the client's own short retries, declare a failed item in its outcome, and raise anything else for a fatal failure.

_Why:_ how a failure is reported decides what the engine does with it (JOB-39). The inference client already retries 502, 503 and 504 in place.

**JOB-150.** A kind whose chunk runs long MUST call `reader.progress.advance_to(done)` as it goes, and `reader.progress.stop_if_cancelled()` between two steps, letting `ChunkCancelled` through.

_Why:_ its job's bar moves, and a cancellation is heard before the chunk ends. A kind that never checks runs its chunk to the end. Progress is no point to resume from: a chunk claimed again starts over.

**JOB-151.** `model_identity` MUST return the model's name and the checkpoint the inference loaded, or nothing for a kind that runs no model. A provenance that cannot be completed MUST NOT fail the chunk.

_Why:_ the checkpoint is what identifies the weights that answered. A server that could not be asked must not cost the chunk its work.

**JOB-152.** The provenance MUST record every parameter but the engine's: `chunk_size`, and what the kind lists in `params_not_in_provenance`, such as a timeout, a count of retries, or a selection of items.

_Why:_ the provenance says what was computed, not how the engine ran it. A selection would copy every identifier into every row.

**JOB-153.** A kind that sends media to the inference MUST declare the types it can send (`supported_media`), take the person's choice as a `media` parameter, and call `refuse_unsupported_media` first in `plan`, so that a job choosing another type is refused whole, the types named. It MUST plan by medium, and a chunk MUST NOT mix tables. `media_chunks` does this for still media; the tracking kind plans one video per chunk (JOB-116).

_Why:_ a job that ran on the images and skipped the point clouds would look finished while doing less than asked. Two media types never go to the same model.

**JOB-154.** A parameter that names a model the inference serves MUST carry `x-pixano-model-task`, with a Pixano task, and no default.

_Why:_ the form offers the models the inference serves for that task. A name written into a kind would be a guess about a deployment.

**JOB-155.** A parameter that destroys something when it is set MUST carry `x-pixano-confirm`, with the text the form shows, and MUST be a boolean with a plain default, not a `default_factory`.

_Why:_ the form turns Run into a confirmation. Pydantic does not publish a factory's value, and the contract suite knows how to set a flag only.

**JOB-156.** A kind whose parameters the generic form cannot build MUST carry `x-pixano-own-form` at the root of its parameter schema, naming the kind's own way in.

_Why:_ the generic form leaves such a kind out.

**JOB-157.** A kind that calls the inference MUST take its address and key from the registry, never from the environment.

_Why:_ a kind must not know about the deployment.

**JOB-158.** What a kind needs from a dataset, and another kind may need too, MUST go in the reader or the writer, or in the modules the kinds share (`kinds/boxes.py`, `kinds/masks.py`, `kinds/inference.py`). A kind MUST NOT import another kind's private helpers.

_Why:_ adding a kind must never mean touching another. A change to the reader or the writer is a change of this contract, made on purpose.

**JOB-159.** A kind that proposes entities MUST ask `writer.entities_with_a_persons_work` before it proposes again an entity a person worked on.

_Why:_ the writer keeps that entity at its rank, so the same model would write a second entity beside it.

**JOB-160.** A kind MUST write the model's own score in the score field its schema declares ([DATA-14](./data-model.md)), and MUST NOT invent one.

_Why:_ a person's edit keeps the model's score, which must be the model's. The detection kind brings it within [0, 1], the range of `confidence` (JOB-109).

## The settings

The worker reads these variables (`packages/pixano-worker/src/pixano_worker/config.py`, `queue.py`). Any PostgreSQL 14 or later serves, with a role allowed to create a schema (JOB-8).

| Variable                        | Default                        | What it is                                                                                                                                                                                              |
| ------------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PIXANO_DATABASE_URL`           | none, required                 | The PostgreSQL of the queue. Its password is masked in the configuration line logged at startup; other log lines carry the database's message as it is ([ARCH-42](./architecture.md#security), target). |
| `PIXANO_INFERENCE_URL`          | none, required                 | The `pixano-inference` server. The worker waits for its `/health` at startup. Required today, also to run the kinds that call no model: see [Open questions](#open-questions).                          |
| `PIXANO_INFERENCE_API_KEY`      | empty                          | The inference's key, sent as a bearer token.                                                                                                                                                            |
| `PIXANO_LIBRARY_DIR`            | none, required                 | The library of datasets, as the worker sees it.                                                                                                                                                         |
| `PIXANO_MEDIA_ROOT`             | none, required                 | The media root, as the worker sees it.                                                                                                                                                                  |
| `PIXANO_INFERENCE_MEDIA_ROOT`   | none, required                 | The same root, as the inference sees it.                                                                                                                                                                |
| `PIXANO_WORKER_ID`              | `host:pid`                     | The worker's identity (JOB-15).                                                                                                                                                                         |
| `PIXANO_WORKER_CONCURRENCY`     | 4                              | Chunks in flight. A cautious start, not measured: the inference's own limit on simultaneous calls is shared with every client, and each call has its own timeout.                                       |
| `PIXANO_WORKER_CHUNK_TIMEOUT_S` | 1800                           | The time limit of a chunk of weight one (JOB-65), above the embeddings kind's worst case, one call and its retries, about twenty minutes.                                                               |
| `PIXANO_WORKER_HEARTBEAT`       | `/tmp/pixano-worker.heartbeat` | The file the heartbeat touches, and the probe reads.                                                                                                                                                    |
| `PIXANO_WORKER_DEMO_KINDS`      | false                          | Registers the demonstration kinds `fake` and `label`. JOB-30 (target) stops registering them.                                                                                                           |

The app reads these for the jobs (`src/pixano/api/settings.py`):

| Variable              | Default | What it is                                                                      |
| --------------------- | ------- | ------------------------------------------------------------------------------- |
| `PIXANO_DATABASE_URL` | none    | The queue. Unset, the jobs routes answer 503 and an import queues no follow-up. |

The settings that decide whether, and with which model, an import asks for its follow-ups (`PIXANO_EMBEDDINGS_AFTER_IMPORT`, `PIXANO_EMBEDDINGS_MODEL`, `PIXANO_STATISTICS_AFTER_IMPORT`) belong to the import and export spec.

The constants that the rules name, with their values today. A rule binds the mechanism, not the value: these are tuning.

| Constant                                                  | Value                                       | Where                               |
| --------------------------------------------------------- | ------------------------------------------- | ----------------------------------- |
| `LEASE_TTL`, `LEASE_REFRESH_INTERVAL`                     | 120 s, refreshed every 40 s                 | `queue.py`                          |
| `MAX_ATTEMPTS`                                            | 5                                           | `queue.py`                          |
| `RETRY_BASE_DELAY`, `RETRY_MAX_DELAY`                     | 15 s, doubled, at most 5 min                | `queue.py`                          |
| `RECLAIM_INTERVAL_S`                                      | 30 s                                        | `runner.py`                         |
| `OUTAGE_BACKOFF_S`                                        | 1, 2, 5, then 10 s                          | `runner.py`                         |
| `CONNECT_TIMEOUT_S` (worker)                              | 5 s, to connect and to borrow from the pool | `__main__.py`                       |
| `UNEXPECTED_ERROR_PAUSE_S`                                | 1 s                                         | `runner.py`                         |
| `UNEXPECTED_ERROR_LOG_EVERY`, `UNEXPECTED_ERROR_LIMIT`    | 60, 60                                      | `runner.py`                         |
| `PLANNING_RETRY_DELAY`                                    | 2 s                                         | `runner.py`                         |
| `PLANNING_WRITE_LOCK_WAIT_S`                              | 10 s                                        | `runner.py`                         |
| `PLANNING_TIMEOUT_S`                                      | 600 s                                       | `runner.py`                         |
| `CHUNK_WRITE_LOCK_WAIT_S`                                 | 300 s                                       | `runner.py`                         |
| `CHUNK_DATASET_BUSY_WAIT_S`, `CHUNK_DATASET_BUSY_RETRY_S` | 30 s, tried every second                    | `runner.py`                         |
| `PROGRESS_INTERVAL_S`                                     | 2 s                                         | `runner.py`                         |
| `SHUTDOWN_GRACE_S`                                        | 30 s                                        | `runner.py`                         |
| `stop_grace_period` of the worker                         | 45 s                                        | `docker-compose.yml`                |
| Open datasets per worker (`_OPEN_DATASETS_MAX`)           | 8                                           | `runner.py`                         |
| `MAX_HEARTBEAT_AGE_S`, `HEARTBEAT_INTERVAL_S`             | dead past 30 s, touched every 10 s          | `config.py`, `__main__.py`          |
| `COMPACT_EVERY_WRITES`                                    | 64                                          | `writer.py`                         |
| `KEEP_OLD_VERSIONS_FOR`                                   | 1 hour                                      | `writer.py`                         |
| A stream's queue (`_SUBSCRIBER_BACKLOG`)                  | 1 000 events                                | `src/pixano/api/jobs/events.py`     |
| `CATCH_UP_SLACK`                                          | 100 identifiers                             | `src/pixano/api/jobs/events.py`     |
| `CONNECT_TIMEOUT_S` (app)                                 | 5 s                                         | `src/pixano/api/jobs/enqueue.py`    |
| `QUEUE_STATEMENT_TIMEOUT_MS`                              | 5 s                                         | `src/pixano/api/jobs/follow_ups.py` |
| Embeddings `chunk_size`                                   | 8 by default                                | `kinds/embeddings.py`               |
| Tracking `window`                                         | 16 frames by default                        | `kinds/tracking.py`                 |
| Tracking `max_retries`                                    | 0 by default, at most 10                    | `kinds/tracking.py`                 |
| Tracking `request_timeout_s`                              | 1 860 s by default                          | `kinds/tracking.py`                 |
| `MAX_STATISTICS_PER_JOB`                                  | 50                                          | `kinds/statistics.py`               |
| Statistics `chunk_size`                                   | 500 by default                              | `kinds/statistics.py`               |

## The routes

All under `/jobs`, in `src/pixano/api/routers/jobs.py`.

| Route                              | What it does                                                                                                                                                                                    |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /jobs/kinds`                  | The kinds the workers declared, with the JSON schema of their parameters. 503 when no worker ever installed the queue (JOB-74); empty only when the queue exists and no worker declared a kind. |
| `POST /jobs`                       | Submits `{kind, dataset_id, params}` (JOB-78). 202.                                                                                                                                             |
| `GET /jobs?limit=`                 | Every dataset's jobs, most recent first: 50 by default, 200 at most.                                                                                                                            |
| `GET /jobs/{id}`                   | One job: its state, its counters, its outcome, `cancel_requested`, `error`, `finalizing`.                                                                                                       |
| `GET /jobs/{id}/quarantine?limit=` | The items a job set aside, in the order they were: 100 by default, 1 000 at most.                                                                                                               |
| `POST /jobs/{id}/cancel`           | JOB-59.                                                                                                                                                                                         |
| `POST /jobs/{id}/retry`            | JOB-51. 409 for a job neither in error nor cancelled.                                                                                                                                           |
| `GET /jobs/events?types=`          | The stream of every job. `types` keeps `state`, `progress` or both; another name is answered 422. No catch-up.                                                                                  |
| `GET /jobs/{id}/events`            | The stream of one job, progress included, resumed from `Last-Event-ID`.                                                                                                                         |

A stream sends a comment every 15 s while it is silent, so that intermediaries keep it open.

## Known limits

What the code does today that a reader must keep in mind. A bullet may name the rules it relates to; it decides nothing itself.

- **What a worker's write sees of a person's saves.** `write` reads through the worker's cached dataset, which sees this worker's writes and the planning of a job, not a save through the app meanwhile. A detection, a segmentation or a track can land beside a mask or a box saved during the job, or name an entity deleted then. Worse, a row a person accepts during the job can go back to pending, overwritten under its identifier, or be deleted as stale (JOB-86, target). Review what a job proposed once it is done.
- **A narrow window in segmentation.** Ensuring an existing masks table takes no lock, so the start of `write` does not refresh the table handles: a planning that opens the dataset again while another job's chunk still writes misses that chunk's last write until its own next write.
- **Each worker holds a PostgreSQL role allowed to create a schema** (JOB-8), and the Compose file gives it the database's own superuser (`docker-compose.yml`). [ARCH-6](./architecture.md#control-plane) (target) takes the worker's credentials away.
- **The app learns of a worker's writes at a job's end** (JOB-73). During a job, what the worker wrote is not visible to a search. A change to `info.json` is the exception on a local dataset (`Dataset.is_stale`).
- **A write that never returns** holds its dataset's write lock in that worker until the worker restarts. That dataset's jobs are postponed at planning, and its chunks, after their inference, wait `CHUNK_WRITE_LOCK_WAIT_S` each in a slot before they are handed back.
- **A URL's host is passed on unchecked.** The worker hands an `http://`, `https://` or `s3://` URI to the inference as it is (JOB-97): only the inference's own allowlist stands between a dataset and an internal address.
- **A medium designated by a path outside the worker's media root** is looked up as bytes in the dataset, which holds none for such a view: it goes to the quarantine as `media not found`.
- **Workers that run different kinds.** A worker that claims the planning or a chunk of a kind it does not run fails it (JOB-33), even when another live worker runs that kind: during a rolling deployment, or with a GPU worker that runs tracking beside a CPU worker that does not, a job can fail with `unknown job kind`.
- **A declaration outlives its kind.** A declaration in `job_kinds` is never withdrawn (JOB-143): a kind no worker registers any more stays offered in the forms and accepted at submission, and every worker fails its jobs, until an operator deletes its row.
- **What holds a detected entity** is read in `entity_id` and `parent_id` only: a message (`entity_ids`) or a relation (`subject_id`, `object_id`) a person made about it does not keep its rank. The tables are listed from the worker's cached metadata: a table another process added since is missed by one write.
- **A detection rerun takes the pending masks of the entities it rewrites**, even when the same entity comes back at the same rank, so a segmentation runs again after every detection.
- **Detection writes each image on its own**: the entities, then the boxes, each a Lance commit, about a tenth of a chunk's time on CPU.
- **Building a vector index** holds the worker's write lock of its dataset for tens of seconds at 50 000 to 100 000 vectors.
- **A statistics chunk holds every annotation of its records in memory**; on a video dataset, a smaller `chunk_size` keeps it bounded.
- **On S3**, `Dataset.write_lock` and `dataset_mutation_lock` do nothing and `Dataset.is_stale` always answers false. No job writes an S3 dataset today, since the worker opens a local library only.
- **Tracking.** The masks and boxes appear at the video's end only, all at once. An interrupted video pays its windows again. A call outlives the worker that asked for it, and the replica answers one call at a time, so the next attempt and the legacy workspace's interactive tracking wait behind it. Dozens of entities in one video may outlast the half hour a call has. A worker whose machine sleeps loses its running chunks, whose leases expire meanwhile. A missing frame is found when its window comes. A tracklet a person's edit of the entity accepted keeps its span, and a later track gets a tracklet of its own beside it.
- **The jobs routes check no caller.** Anybody who reaches the app can submit, cancel or run again any job; `x-pixano-confirm` is a prompt of the form, not an access control. [ARCH-35](./architecture.md#security) (target) authenticates every route.
- **The streams connect without a bound.** Neither connection of a stream has the bound of JOB-80: they wait for psycopg's default. A stream reaches the queue after its headers (JOB-77, target).
- **A database that fails after a route connected** is answered 500, not 503 (JOB-74).
- **A stop during a planning or at startup.** The loop waits for a planning within its turn, up to `PLANNING_TIMEOUT_S`, and the signal handlers are set only once the worker waited for the database and the inference: a supervisor that kills the worker meanwhile kills its chunks with it, without handing them back (JOB-26).

## Writing a job kind

How to add a kind, in the order of the work. The rules of [The job-kind contract](#the-job-kind-contract) say what it must do; this section says how.

1. **Write its parameters**: a model that inherits `JobParams`, with `Field` constraints. Give a model parameter `MODEL_TASK_MARKER` and no default, a destructive flag `CONFIRM_MARKER`, a kind the generic form cannot drive `OWN_FORM_MARKER` (all in `kinds/base.py`).
2. **Write `plan(reader, params)`**: check everything that can refuse the job (media types, the tables it needs, `require_served` for its model), then yield `Chunk(payload=…, task_count=…, weight=…)`. For media, `media_chunks(reader, params.media, chunk_size)` does the split.
3. **Write `process(reader, payload, params)`**: read what the payload designates, call the inference, and return a result. Find and designate media with `chunk_media(reader, table, view_ids)`; classify a failed call with `classify`; when every still medium is refused, call `blame_the_server_or_the_media` (JOB-45).
4. **Write `outcome(result, payload, task_count)`** when the kind skips or quarantines items. Build each item with `quarantined_item(item_id, reason, record_id, **detail)`.
5. **Write `write(writer, result, payload, params)`**: build rows with `writer.table_schema(table)`, spread `writer.provenance()` into each, and write with `writer.replace(table, key, rows, entities, covers)`.
6. **Add `prepare` or `finalize`** only when the kind needs them, and `model_identity` when it runs a model (`InferenceServer.model_identity`).
7. **Register it** in `default_registry`, and add its example to `CONTRACT_EXAMPLES`.

**Choosing the key.** The key of `replace` is the smallest thing the output is about: an image for detection and segmentation, a video and an entity for tracking. A key that does not depend on the chunking lets one item be processed again alone.

**What the reader offers** (`packages/pixano-worker/src/pixano_worker/reader.py`):

- `reader.dataset` and `reader.media`: the dataset, opened when first used, and the media resolver.
- `reader.ids(table, where)`: a table's identifiers, by pages of 2 000, for planning. `reader.count(table, where)` counts.
- `reader.media_tables(media_type)`: the tables that hold media of a type.
- `reader.rows(table, ids)`: rows by identifier.
- `reader.read(table, where)`: the rows matching a filter, for `process`, which has no writer. Not paged: the filter must bound what it reads.
- `reader.image_size(table, view)`: an image's `(width, height)`, as the dataset records it, else from its header; `None` when unreadable. A mask's `size` is `[height, width]`.
- `reader.resolve_media(table, view)` and `reader.open_media(table, view)`: a medium designated for the inference, and the medium itself, its file else its bytes.
- `reader.progress`: where a long chunk reports and hears a cancellation. The reader given to `plan` has no chunk: its progress counts nothing.

**What the writer offers** (`packages/pixano-worker/src/pixano_worker/writer.py`):

- `writer.provenance()`: the provenance fields of a row (JOB-95).
- `writer.replace(table, key, rows, entities, covers)`: rows with, optionally, one entity each, sharing its identifier; `covers(row, entity)` says which previous rows the write is about.
- `writer.drop_pending(table, with_entities, covers)`: for a `prepare` asked to replace the previous proposals.
- `writer.ensure_label_field()`: the entity field a class goes into, `category` added when there is no text field.
- `writer.ensure_table(slot)`: the canonical table of an annotation slot, added when missing. Call it from `prepare`, and again before writing, for a worker whose cached dataset predates the table.
- `writer.table_schema(table)` and `writer.read(table, where)`: the schema to build rows with, and rows to check outputs against.
- `writer.entities_with_a_persons_work(entity_ids, own_table)`, and `is_a_persons_work(row)` beside it.
- For embeddings: `writer.write_media_embeddings(...)`, `writer.empty_embeddings(model, checkpoint)`, `writer.index_embeddings(model)`.
- For statistics: `writer.ensure_statistics(definitions)`, `writer.write_statistics(level, rows, columns)`, `writer.forget_object_statistics(record_ids, kept)`, `writer.record_computed_statistics(definitions)`.

**Geometry** shared by kinds lives in `kinds/boxes.py` (where a box lands in pixels, how much two boxes overlap) and `kinds/masks.py` (how much two masks overlap, the checks a mask passes before pycocotools reads it).

**When the reader or the writer lacks something**, add it there, for every kind, and document it here.

## Open questions

- **The routes of the worker** ([ARCH-24](./architecture.md#execution-plane) to [ARCH-28](./architecture.md#execution-plane), targets). [`architecture.md`](./architecture.md#open-questions) leaves to this spec the shape of the worker's API: a claim, a heartbeat, a lease. The proposal there is a group of routes under `/internal/v1/worker/`. The spec PR that answers it amends every rule that holds only until ARCH-6, ARCH-24 or ARCH-26, in its own words or through JOB-4: JOB-1, JOB-4, JOB-5, JOB-7, JOB-8, JOB-14, JOB-24, JOB-28, JOB-32, JOB-33, JOB-79 and JOB-143.
- **The worker without the inference.** Does [ARCH-59](./architecture.md#inference-plane) hold for `pixano-worker` too, as [`architecture.md`](./architecture.md#open-questions) asks? Today it refuses to start when `PIXANO_INFERENCE_URL` is not set, also to run the kinds that call no model (JOB-14).
- **How long are jobs and their events kept?** Nothing deletes them today, and the job identifier in a row's provenance is an opaque label for that reason. The answer comes with the accounts and their rights.
- **What does a fresh client see of a job's history?** The stream of one job replays its whole history on its first connection, 6 250 events for a job of 50 000 images. The options: a bound, or a `since` parameter.
- **Should a write's wait for a busy dataset grow with the chunk's weight?** Today it does not: a dataset held past `CHUNK_DATASET_BUSY_WAIT_S` sends a whole video back to the queue (JOB-91), which then pays its windows again. The options: a fixed wait, as today, so that the chunk waits its turn in the queue rather than in a slot; or a wait that grows with the weight.
- **Listing jobs reads five correlated subqueries per row** (the outcome's three, `finalizing`, the progress of running chunks): 168 to 281 ms for 50 jobs at 256 000 chunks with the first three. The options: counters written when a chunk completes, which amends JOB-50, or a covering index on `(job_id, state)`.
- **What an import's follow-ups cost.** Each embeddings job and the statistics job compute the whole dataset again (JOB-139, JOB-140): an add import of a few images into a dataset of 10 000 holding three models runs about two hours of inference on the CPU stack. Two add imports in a row queue the same jobs twice, embeddings and statistics. The options: a mode of each job that computes only what the import added (the media a model's table lacks, the records with no value), and skipping a follow-up whose job is still to run.
- **How a chunk's weight becomes its time limit** (JOB-65, chosen while implementing, not decided). Today a kind weighs a chunk in inference calls, and the worker gives it its weight times `PIXANO_WORKER_CHUNK_TIMEOUT_S`: a deployment that lowers the setting to fit its fast kinds sends back long chunks the inference would still have answered. The options: the weight multiplies the deployment's limit, as today, so that a slower deployment raises one number for every kind; or the kind gives the chunk a duration of its own, computed from its own timeouts, exact for each kind but out of the deployment's hands.
- **A refused medium designated by URL** (JOB-47). Refused with the rest of its chunk, it goes to the quarantine today. The options: the quarantine, or a retry of the chunk with a reason that names what to check, a host missing from the inference's allowlist or a presigned URL expired.
- **Which boxes `replace_previous` deletes for a detection job asked for classes** (JOB-111, chosen while implementing, not decided). The options: only the pending boxes of the classes asked for, as today, so that a job asked for dogs touches nothing but dogs; or every pending box of the kind, so that the parameter means what its confirmation says, and the classes restrict only what the job writes.
- **How the segmentation kind writes its masks** (provisional, still to be confirmed). Today it writes one mask per box already on an image, a detection's or a person's, of any model and status, naming an entity that exists. One call per image carries all its boxes, sorted by identifier, in whole pixels, rounded and cut at the image's edges, asking one mask per box (`multimask_output` false). The mask names the box's entity, pending, with no entity of its own, keyed by kind, model and image. An image with no box left is skipped with no call, and its pending masks are replaced by nothing. An answer that is not exactly one readable mask per box, of the image's height and width, quarantines the image, which keeps its masks, and an empty mask is not written. `prepare` gives the dataset a masks table when it has none. Planning refuses a dataset without a table of boxes or of entities, and one with no box to segment unless `replace_previous` is set, which clears every pending mask of the kind, whatever its model, and leaves the boxes and the entities. No mask is written on an entity that holds, on that image, a mask a person drew or accepted, nor, as JOB-113 says, one that overlaps such a mask of the same class or of none past `overlap_threshold`; another model's pending mask blocks nothing, and a person's mask protects its entity on its own view only. `write` reads the boxes and the person's masks again, and drops a mask whose box moved, went or changed entity. To confirm or change: a mask carried by its box's entity, or by an entity of its own; a skipped image whose masks are replaced by nothing, or left as they are; what `replace_previous` clears. Beside it, entities are left named by nothing: a box rejected while its entity keeps a model's pending mask leaves the entity named by nothing after a segmentation rerun, and so do a segmentation with `replace_previous`, a box moved to another entity, and a person's box deleted under a model's pending mask. The proposal: segmentation's write, and `drop_pending` on masks, delete the entities their dropped masks were the last to name. And a box rejected while its entity holds a person's mask comes back on a second entity: should detection be protected by the bounds of a person's mask too?

## Decision log

- 2026-11-24: the six choices of the tracking job's boxes (JOB-123 to JOB-125), made while implementing on 2026-11-19, confirmed by @vmulet-benzo; the approval of this spec PR confirms them ([#878](https://github.com/pixano/pixano/pull/878)).
- 2026-11-25: the worker registers no demonstration kind (JOB-30, target), decided by the team ([#878](https://github.com/pixano/pixano/pull/878)).
- 2026-11-25: first version, moved from docs/specs/backend-processing.md and docs/specs/writing-a-job-kind.md, where these decisions were written from 2026-09-14 on, with the job entries of docs/OPEN_QUESTIONS.md. The job-kind contract is a section of this spec, not a spec of its own ([#878](https://github.com/pixano/pixano/pull/878)).
