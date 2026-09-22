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

### `plan(dataset_id, params) -> Iterable[Chunk]`

Splits the work. It runs in the worker, not in the application: dividing by video, by image or
by selection is the kind's business, and kind code only ever runs on that side.

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
lists in `params_not_in_provenance` (a request timeout, a retry count).

A kind whose `source_type` is `model` also gets `review_status = "pending"` in its
provenance: its rows arrive to be reviewed. A human's annotation, or a demonstration kind's,
carries no status. And `replace` honours the review: rows a human accepted, corrected or
rejected keep their rank and are never touched by a rerun, which replaces the pending rows
only.

### `prepare(writer, params)` — optional

Runs once per job, under the planning lease, before `plan`; never for a replayed chunk, and
never for a job retried with its chunks. The default does nothing, and most kinds keep it: it
exists for a state the chunks cannot each restore on their own, such as emptying a table
before refilling it. Three rules, the first two checked by the suite:

- **Idempotent.** A planner that dies after `prepare` lets its lease expire and the next one
  does both again, so twice must leave the dataset as once does.
- **Nothing is destroyed unless an explicit parameter asks for it.** A job with default
  parameters never loses what the dataset holds.
- **No `finalize` in return** until a kind needs one: what should happen at the end of a job
  is designed then, not by symmetry.

### `process(payload, params)` then `write(writer, result, payload, params)`

Separate because they fail differently: an inference call can be retried, a write must never
be half done. Both run in a thread — the contract stays synchronous, and the worker's event
loop keeps the database, the lease and the time limit for itself.

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
quarantine.

### `outcome(result, payload, task_count) -> Outcome`

Optional. Says what each task of the chunk became: **produced**, **skipped** — the calculation
does not apply, such as a record without an image for an image job, which is not a failure —
or **quarantined**, one `QuarantinedItem` per failed item. The default is "every task
produced", which is right for a kind that neither skips nor loses anything.

The counts must add up to `task_count` exactly. The engine refuses a chunk whose outcome does
not, and the contract suite checks it: an outcome that is quietly wrong would falsify everything
shown about the job. It exists because progress alone cannot tell the truth — a job over a lidar
dataset reaches 26 766 / 26 766 having embedded 404 images.

`write` receives a writer, not a dataset: a kind cannot open a dataset itself. That is what
will let a dataset's writes be serialised across workers one day without touching any kind.

---

## 2. Writing, and why it must be idempotent

Results go to LanceDB while progress goes to PostgreSQL. Two stores, so the two writes cannot
share a transaction: a worker that dies between them redoes the chunk, and a chunk whose lease
expired can be taken over mid-flight. **Replaying must produce the same content, never
duplicates.**

`writer.replace(table, key, rows)` is how. It derives each row's identifier from the _work_ —
the kind, the key, the rank — never from the job, so a resubmission replaces instead of
minting new rows. Then it deletes what a previous run left beyond the current output, which is
the step plain replacement misses: a model that detected five objects and now sees two would
otherwise strand three rows nothing would ever clean up.

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
| `source_metadata` | the job identifier, as JSON                                          |

`source_type` is the schemas' vocabulary, not ours: writing `job` is refused at write time, and
rightly so. What matters to a reviewer is whether an annotation came from a model, not which
cog wrote it. **A kind that runs no model must not claim `model`** — the fake and label kinds
both declare `other`.

---

## 4. Review status — not yet

The plan has every pre-annotation arriving in an "to review" state, with a queue to accept,
correct or reject. **The schemas carry no such field today**, so nothing here can set one. It
is a schema addition, and it belongs with the pre-annotation kinds that need it rather than
with the engine.

Until then, provenance is what tells a reviewer an annotation came from a job.

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
    registry.register(MyKind())      # ← the only engine file a new kind touches
    return registry
```

A real kind goes outside the `demo_kinds` block. That block exists because the demonstration
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
