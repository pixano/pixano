# Writing a job kind

**Status:** Frozen contract. Changing it means changing every kind, so change it deliberately.
**Audience:** anyone adding a processing to the backend — pre-annotation, statistics, indexing.

A job kind is a plugin. It brings its parameters, knows how to split its work, how to process
a batch and how to write what it produced. The engine — claiming, leasing, recovery, progress,
cancellation — knows nothing of what is inside, and adding a kind must never require touching
it. The proof is mechanical: `tests/test_kind_contract.py` runs the same suite over every
registered kind, and adding a kind without an entry in `CONTRACT_EXAMPLES` fails it.

---

## 1. The contracts

### `Params` — a pydantic model, inheriting `JobParams`

```python
class MyParams(JobParams):
    model: str = Field(default="clip")
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
```

Inheriting `JobParams` is what forbids unknown fields, and that is not tidiness: it makes
pydantic emit `additionalProperties: false` in the schema published to the application, which
is what lets a misspelled parameter be refused at submission. Without it, `thresholdd` passes
validation and is silently ignored — the user gets a job running on defaults with no
indication why.

### `plan(reader, params) -> Iterable[Chunk]`

Splits the work. It runs in the worker, not in the application: dividing by video, by image or
by selection is the kind's business, and kind code only ever runs on that side. The reader is
how it reads the dataset without opening one; a
kind whose work fits in its parameters ignores it.

Two requirements the suite checks. **Every chunk carries at least one task**, or it consumes a
turn without advancing anything. And **planning twice describes the same work**: a job
replanned after an outage must not describe something different from what was partly executed.

A chunk's payload is opaque to the engine, and must be a JSON object.

### `model_identity(params)` and `provenance_params(params)` — provenance

Every row a kind writes through `writer.provenance()` says by itself how it was produced:
`source_name` is the kind, `source_metadata` carries the job identifier (an opaque run
label), the kind, the model and its version when the kind runs one, and the parameters.
The writer fills it; the kind only answers two questions. `model_identity(params)` returns
the model's name and whatever the inference exposes beyond it — the checkpoint it loaded —
or `None` for a kind that runs no model; it runs in the job's thread, so asking the server is
allowed, but a provenance that cannot be completed must not fail the chunk. The parameters
recorded are all of them but the engine's: `chunk_size` by default, plus whatever the kind
lists in `params_not_in_provenance` (a request timeout, a retry count) — and a selection of
items, such as the label kind's `record_ids`, which would copy every identifier into every row.

A kind whose `source_type` is `model` also gets `review_status = "pending"` in its
provenance: its rows arrive to be reviewed. A human's annotation, or a demonstration kind's,
carries no status. And `replace` honours the review: rows a person accepted keep their rank
and are never touched by a rerun, which replaces the pending rows only.

### `prepare(writer, params)` — optional

Runs once per job, under the planning lease, **after** `plan` has produced work and before
the chunks are recorded; never when the plan was refused or empty, never for a replayed chunk,
and never for a job retried with its chunks. After, so that everything that can refuse the
job — a model the dataset's embeddings were not computed with, say — refuses it before
anything is destroyed. So `plan` must not rely on what `prepare` will do. The default does
nothing, and most kinds keep it: it
exists for a state the chunks cannot each restore on their own, such as emptying a table
before refilling it. Two rules, both checked by the suite:

- **Idempotent.** A planner that dies after `prepare` lets its lease expire and the next one
  does both again, so twice must leave the dataset as once does.
- **Nothing is destroyed unless an explicit parameter asks for it.** A job with default
  parameters never loses what the dataset holds.

What must happen at the end of a job is `finalize`'s, below — not a mirror of `prepare`.

It runs under the worker's write lock of the dataset, as a chunk's `write` does: the worker's
chunks of other jobs may be writing the same dataset meanwhile, in other threads, and the
dataset's own lock never waits. Another process writing the dataset — a person's save, another
worker, an import — still makes that lock raise `DatasetBusyError`. Let it through: the runner
then leaves the job in `planning` and plans it again a moment later, `prepare` included
(backend-processing §10), whereas any other error fails the job. The runner's own lock is
waited for ten seconds at most (`PLANNING_WRITE_LOCK_WAIT_S`): past them — a long write of this
worker on the dataset, or one that hangs — the job is postponed the same way. And the whole
planning, `plan` then `prepare`, has ten minutes (`PLANNING_TIMEOUT_S`): past them the job
fails, and a `prepare` that had not started never starts. So a `prepare` must stay far below
that, on the largest dataset it will meet.

### `finalize(reader, writer, params)` — optional

Completes the job once every chunk of it is done: what only makes sense over the whole result,
such as an index trained on every vector the job wrote. No chunk can do it — each sees its own
work — and the last chunk to finish does not know it is the last.

A kind that overrides it gets a **final chunk**, recorded at planning with the others but
`waiting`, last in rank and without a task. When every other chunk is done — none failed, none
left, the job not cancelled — whoever settles the job puts it in the queue, and any worker runs
it like a chunk: under a lease, with the chunk's time limit, cancelled with the job, handed back
after a transient failure, retried by `POST /jobs/{id}/retry`. The job reads `done` only after
it. It never runs when a chunk failed or the job was cancelled; a retry that brings the failed
chunks through runs it then, and the worker's recovery pass runs it for a retried job that had
nothing left to reopen — cancelled while its last chunks ran (backend-processing §8.5). Its tasks
are none, so the job's progress and outcome are those of its work. A kind that does not
override it has no final chunk, and its jobs settle with their last chunk as before.

It runs in a thread, under the worker's write lock of the dataset, as a chunk's `write` does,
on the dataset **reopened outside the cache**: it must see what every worker wrote, not what
this one had open. Raise `TransientError` for a failure of circumstance. A `DatasetBusyError` —
another process writing the dataset, a person's save — is handed back to the queue the same
way, not failed: the chunks are all done, and the job should not lose them for a save. Any other
error fails the final chunk, and the job with it. Three rules, the first two checked by the
suite:

- **Idempotent.** A worker that dies while finalizing lets its lease expire, and the final
  chunk runs again, maybe elsewhere: twice must leave the dataset as once does. The suite runs
  a whole job with `finalize` once and twice and compares the rows.
- **Deletes no row.** It may rebuild what derives from the rows — an index replaces the
  previous one — but the rows stay as the chunks left them. The suite compares the rows
  before and after it.
- **Reads the dataset, never the chunks.** Their payloads and results are gone, and other
  workers wrote part of them: what the job produced is what the dataset holds.

### `process(reader, payload, params)` then `write(writer, result, payload, params)`

Separate because they fail differently: an inference call can be retried, a write must never
be half done. Both run in a thread — the contract stays synchronous, and the worker's event
loop keeps the database, the lease and the time limit for itself. `process` receives a reader,
as `plan` does: a chunk carries what designates its work, never the data itself.

**How a failure is reported decides what the engine does with it.** Three families:

| Family        | What the kind does                             | What the engine does                                                                  |
| ------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------- |
| **Transient** | raises `TransientError`                        | sends the chunk back after a growing delay; sets it aside only after its last attempt |
| **Item**      | raises nothing; declares the item in `outcome` | finishes the chunk and puts the item in quarantine, with its reason                   |
| **Fatal**     | raises anything else                           | fails the chunk, and the job with it                                                  |

A brief hiccup can still be retried in place — the inference client already does so for 502,
503 and 504. Raise `TransientError` for what outlasts that.

**Blame an item only on an answer, never on a silence.** A server that refused a request has
told you something about its content; a server that did not answer has told you nothing. The
embeddings kind learnt this on the real stack: during an inference restart, one call went
through and the next were refused, and "not every image failed" sent seven healthy images to
quarantine. When the server refuses every medium of a chunk, the kinds that call the inference
ask it whether it is at fault through one shared helper (`blame_the_server_or_the_media`, in
`kinds/inference.py`; backend-processing §8.2). What it can check depends on how each medium
was designated, which the media resolver says (`ResolvedMedia.designation`: `path`, `url` or
`bytes`): a path is resent as the bytes this worker reads from its file, a URL is not checked
and goes to quarantine with the rest.

### Media types

A kind that reads media declares `supported_media`, the types it can send to the inference
(`image`, `video`, `point_cloud`, `text`), and takes the user's choice as a `media`
parameter. Its `plan` calls `refuse_unsupported_media(params.media)` first: a job choosing a
type the kind cannot process is refused whole, the types named — never run on part of what
was asked. Plan by medium, one chunk per table, and quarantine a medium under its own
identifier with its `record_id` in the detail: the panel shows the record.

A kind whose parameters the generic submission form cannot build — the statistics' definitions,
which the application sends itself — carries `OWN_FORM_MARKER` (`x-pixano-own-form`) at the root
of its schema, naming the kind's own way in. The generic form is to leave it out.

### `outcome(result, payload, task_count) -> Outcome`

Optional. Says what each task of the chunk became: **produced**, **skipped** — the calculation
does not apply, such as a record without an image for a kind that plans by record, which is
not a failure —
or **quarantined**, one `QuarantinedItem` per failed item. The default is "every task
produced", which is right for a kind that neither skips nor loses anything.

The counts must add up to `task_count` exactly. The engine refuses a chunk whose outcome does
not, and the contract suite checks it: an outcome that is quietly wrong would falsify everything
shown about the job. It exists because progress alone cannot tell the truth — a job over a lidar
dataset reaches 26 766 / 26 766 having embedded 404 images.

`write` receives a writer, not a dataset: a kind cannot open a dataset itself. That is what
will let a dataset's writes be serialised across workers one day without touching any kind.

### What the reader and the writer offer the statistics kind

A kind reaches the dataset through these two only. The statistics kind brought
(backend-processing §22):

- **`reader.read(table, where)`** — the rows of a table matching a filter, for `process`, which
  runs outside the write lock and has no writer: a chunk's objects and boxes. Not paged, so the
  filter must bound what it reads — a chunk's records, not a whole table.
- **`reader.image_size(table, view)`** — an image's `(width, height)` in pixels, as the dataset
  records it, else from the image's header; `None` when the worker cannot read one.
- **`writer.ensure_statistics(definitions)`** — the statistics tables of their levels and a
  nullable column per statistic, added to the dataset where missing. Call it from `prepare`,
  and again before writing. Columns the dataset holds already are answered from its tables,
  without its lock.
- **`writer.write_statistics(level, rows, columns)`** — the values of these columns, one row
  per record or per object, naming its record, and its object for an object: the dataset makes
  the row's identifier the record's or the object's. A merge that writes these columns only,
  the other statistics of each row kept, and leaves out the rows of records and objects deleted
  since they were measured. Answers the identifiers of the rows written.
- **`writer.forget_object_statistics(record_ids, kept)`** — deletes the statistics of these
  records' objects but those kept — the rows the chunk wrote: objects deleted since the last
  computation, or since the chunk measured them.
- **`writer.record_computed_statistics(definitions)`** — records in the dataset that this job
  computed these statistics, now; the explorer names and dates its columns with it. For
  `finalize`: it changes the dataset's description, never a row.

---

## 2. Writing, and why it must be idempotent

Results go to LanceDB while progress goes to PostgreSQL. Two stores, so the two writes cannot
share a transaction: a worker that dies between them redoes the chunk, and a chunk whose lease
expired can be taken over mid-flight. **Replaying must produce the same content, never
duplicates.**

`writer.replace(table, key, rows)` is how. It derives each row's identifier from the _work_ —
the kind, the model, the key, the rank — never from the job, so a resubmission replaces instead
of minting new rows, and another model's rows for the same key are left alone. Then it deletes
exactly what a previous run of the same model left beyond the current output, found by the
prefix the key's identifiers share. That is the step plain replacement misses: a model that
detected five objects and now sees two would otherwise strand three rows nothing would ever
clean up.

**Choose the key carefully.** It should be the smallest thing the output is about — usually a
record id. The `label` kind uses one key per record, so re-labelling one record does not depend
on the chunking that first processed it; the `fake` kind uses one key per chunk, which is
simpler and adequate because nothing ever re-runs a fraction of it.

---

## 3. Provenance

Every row a job writes says where it came from. The writer fills it in, so no kind has to
remember to:

| Field             | Value                                                                |
| ----------------- | -------------------------------------------------------------------- |
| `source_type`     | what the kind declares — `model`, `human`, `ground_truth` or `other` |
| `source_name`     | the kind's name                                                      |
| `source_metadata` | the job, kind, model and parameters, as JSON (see above)             |

`source_type` is the schemas' vocabulary, not ours: writing `job` is refused at write time, and
rightly so. What matters to a reviewer is whether an annotation came from a model, not which
cog wrote it. **A kind that runs no model must not claim `model`** — the fake and label kinds
both declare `other`.

---

## 4. Review status

Every entity annotation schema carries `review_status`: `pending` or `accepted` on a model's
row, empty on any other. A kind never sets it. The writer marks a `model` kind's rows `pending`
(§1), and from there people decide, through rules the API applies to every kind alike
(`src/pixano/api/review.py`; [backend-processing §19](./backend-processing.md)). A person
accepts a row as it is, or by saving an edit of it, which stores it `accepted` with the
model's provenance and score; a person who rejects a row deletes it, so a rejected proposal
leaves no row behind. What it means for a kind:

- **Accepted rows are frozen.** `replace` leaves a row a person accepted where it is, rank
  included, and replaces the pending rows only. A model's row with no status —
  re-imported from JSONL — counts as pending: the writer reads it from the definition the
  application reads too, `pixano.schemas.NOT_REVIEWED_STATUSES`. A person's row has no status
  either, and is never taken for a pending one: `replace` reaches only the identifiers the kind
  derived itself.
- **Fixing what an entity says accepts.** A person who changes an entity a kind wrote or
  annotated — the class of a detected object, for instance — saves an edit of every model
  annotation that names it and is still pending: the API makes them `accepted`, so the next run
  leaves them alone instead of writing its own values back. Any field of the entity counts but
  its links and timestamps (`ENTITY_SYSTEM_FIELDS`). A kind that writes what it found on an
  entity gets this without asking — and so does a kind that writes its rows on another kind's
  objects, whose pending rows a person's fix of the object accepts, though nobody looked at them
  (backend-processing §19).
- **Nothing to register — for a kind an interface can review.** Which kinds those are is one
  predicate, `pixano.schemas.is_reviewable_annotation`: every entity annotation but tracklets,
  relations and text spans. The next record to review is found by scanning those tables — for
  rows on a view an interface can show for review, `pixano.schemas.is_reviewable_view`: not a
  video or its frames —, the interface reads the status from any row, and the export by status
  filters those tables only.
  A kind writing boxes, 3D boxes, masks, keypoints, paths or classifications is reviewable as
  it stands. A model's tracklets, relations or text spans stay outside the review — the queue
  does not wait for them, an export by status does not filter them (a model's tracklet goes
  with its entity, as its structure) — until an interface can review them; the kind then leaves
  the list in `src/pixano/schemas/annotations/review.py`.
  What is not an entity annotation — an embedding, a message — is never reviewed.
- **The score belongs to the model.** A person's edit keeps the row's score, as it keeps its
  provenance: write the model's own score there, never a placeholder. Each schema names its
  score fields in `MODEL_SCORE_FIELDS` — `confidence` on a box, `confidences` on a
  classification. A new schema with a score declares it there. A list of scores that scores
  another field position by position — one score per label — also says so in
  `MODEL_SCORE_ALIGNMENT` (`{"confidences": "labels"}` on a classification): when a person
  changes the labels, each label the model gave keeps the model's score and a label the person
  adds takes the score sent with it. A guard test (`tests/schemas/test_review.py`) fails on a
  score-like field left undeclared, and on a list of scores that declares nothing it scores.

---

## 5. Registering

```python
# kinds/__init__.py
def default_registry(inference_url: str = "", api_key: str = "", demo_kinds: bool = False) -> Registry:
    registry = Registry()
    if demo_kinds:                   # fake and label: for the engine's tests and the demo only
        registry.register(FakeKind())
        registry.register(LabelKind())
    registry.register(EmbeddingsKind(inference_url, api_key))
    registry.register(MyKind(inference_url, api_key))  # ← the only engine file a new kind touches
    return registry
```

A kind that calls the inference takes its address and key from the registry, as the embeddings
kind does, rather than reading the environment: a kind should not know about the deployment. A
kind that calls nothing, as `fake` and `label`, takes no argument. A real kind goes outside the
`demo_kinds` block. That block exists because the demonstration
kinds write wherever they are told and have no place in a shared deployment; the local compose
enables them with `PIXANO_WORKER_DEMO_KINDS`.

Each worker publishes its registry into `job_kinds` at startup, which is the only bridge
between the application and the worker — they share no code. The application validates a
submission against what a worker has declared it can run, so a kind no worker has ever declared
is refused at submission. A declaration is not withdrawn when its worker stops — liveness of
workers is step 4's — so a job for a declared kind whose workers are all down is accepted, and
waits until one returns.

Then add an entry to `CONTRACT_EXAMPLES` in `tests/test_kind_contract.py`. A kind without one
fails the suite on purpose: a kind nobody knows how to exercise has escaped the contract.
