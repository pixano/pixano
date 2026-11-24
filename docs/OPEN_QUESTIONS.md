# Open questions

> A running list of undecided architecture / packaging questions. Add an entry
> when a decision is deferred; remove it (and record the outcome in the relevant
> doc or code) once resolved.

## Per-dataset layout preference — accepted limitations

**Status:** open (deliberate trade-offs, shipped knowingly).

The workspace remembers how a user arranges a dataset's widgets and replays it on
the dataset's other records (`ui/apps/web/src/lib/workspace/datasetLayout.ts`,
`datasetLayoutRepository.ts`; see FRONTEND_ARCHITECTURE.md §4). These limits were
accepted to keep the first version small — each is a decision, not an oversight.

- **Storage is browser-local.** The arrangement never follows a user across
  machines or browsers. `DatasetLayoutRepository` exists precisely so this can
  move to a user-scoped preference endpoint by swapping the implementation
  injected into `WorkspaceManager`, with no call-site changes.
- **No way to forget an arrangement.** `clear()` was dropped from the port when
  "Reset layout" was redefined as "restore what this record opened with", leaving
  no caller. Consequences: a dataset can never go back to purely automatic
  placement once arranged, and entries for deleted datasets linger in
  `localStorage`. Re-adding `clear()` plus a "Forget arrangement" action is the
  fix if either becomes a real complaint.
- **Only view-backed widgets are remembered.** A widget dragged in from the
  palette has no counterpart in the next record's views, so nothing would restore
  it onto. "Fit layout" does re-tile them on screen; they just are not persisted.
- **Concurrent tabs: last writer wins.** No `storage` event listener, so two tabs
  on the same dataset overwrite each other's arrangement.
- **The arrangement no longer adapts to the viewport.** Before this feature every
  record opened with a placement recomputed for the current screen. Once a
  dataset has been arranged, its records replay cell coordinates captured on
  whatever screen the user arranged them on, and nothing re-fits automatically —
  an arrangement built on a large display can extend past the fold on a laptop.
  "Fit layout" is the manual escape hatch; re-fitting on viewport change (or
  storing the viewport alongside the arrangement and re-planning when it differs
  markedly) is the fix if this bites.

## How should `tri3d` be declared for `uv`?

**Status:** open.

`tri3d` is used by `src/pixano/datasets/builders/folders/builder_3d.py`
(`Dataset3DBuilder`) to import tri3d-supported 3D datasets (nuScenes, Argoverse, …).
It is currently declared **nowhere** in `pyproject.toml`, so `uv sync` (core deps +
the default `test` group) never installs it — you must `pip install tri3d` by hand.

It is treated as **optional by design**: `datasets/builders/__init__.py` guards
`Dataset3DBuilder` behind `try/except ImportError`, and the builder test
`importorskip`s it, so the rest of Pixano works without it. The gap is only that
there is no *supported* install path.

Options:

- **A — opt-in (matches the current optional design).** Add a group to
  `[dependency-groups]`:
  ```toml
  [dependency-groups]
  threed = ["tri3d >= 0.2.0, < 0.3.0"]
  ```
  Install 3D support with `uv sync --group threed`. Keeps the default install light
  (`tri3d` pulls in `numba` + `llvmlite`).
- **B — installed by default.** Add `threed` to `[tool.uv] default-groups` (or put
  `tri3d` in core `dependencies`) so a plain `uv sync` installs it for everyone.
  Simplest for 3D users, but forces `tri3d` + `numba` + `llvmlite` into every
  install and softens the "optional" design.

**Leaning:** A (opt-in), but undecided — needs a team call. Whichever is chosen,
declaring it in `pyproject.toml` also removes the current manual `pip install`
step. Tested against `tri3d 0.2.2`.

## Entity reassignment — a hook with a single caller

**Status:** open (accepted deliberately; revisit if no second caller appears).

A `PayloadBuilder` (`ui/apps/web/src/lib/annotations/payloadBuilders.ts`) may
declare an optional `geometryForEntity` hook, and exactly one kind does:
`classification`, whose labels mirror its entity's own label, so moving it
without rewriting them would leave a chip asserting a class the annotation no
longer belongs to. Every other kind carries geometry independent of its entity.

The hook sits on the kind's builder, not on the call that opens the entity form.
It was first an option of `beginEntityReassign`, passed by the chip's
double-click alone; the widget toolbar and the `E` shortcut open the same form
without knowing the kind, and saved the previous class under the new entity.

An abstraction with one caller is normally speculative generality. It was kept
because the concrete alternative is `if (annotation.kind === "classification")`
inside shared code — the exact coupling the plugin architecture exists to
prevent, and the point at which the next kind adds its own `else if`. The hook
keeps the shared layer ignorant of which kinds exist.

Two things to watch:

- **If a second caller never appears**, and the classification kind's labels are
  ever stored differently (or derived at render time from `annotation.entity`
  rather than duplicated into `geometry`), the hook loses its only reason to
  exist and should be removed with it.
- **The shared layer applies the hook's answer by writing to the collection.**
  That is deliberate — `reassignEntity` re-reads the live annotation so the
  update body carries the entity id it just assigned. The hook itself is a pure
  function returning the new geometry, or `null` to refuse the move.

## `replace_previous` with classes clears only the pending boxes of those classes

**Status:** open (chosen while implementing, not decided).

A rerun of the same model replaces its own pending rows, and a detection job
asked for some `classes` replaces only the pending boxes of those classes: asked
for dogs, then for bicycles, it keeps the dogs (backend-processing §19). A job
that also sets `replace_previous` clears, before detecting, only the pending
boxes of the classes it was asked for, whatever their model
(`DetectionKind.prepare` and `_classes_covered` in
`packages/pixano-worker/src/pixano_worker/kinds/detection.py`, through
`JobWriter.drop_pending`). That second scope was chosen while implementing, by
analogy with the first; nobody decided it.

Options:

- **Clear only the pending boxes of the classes asked for**, as today: a job
  asked for dogs touches nothing but dogs.
- **Clear every pending box of the kind, whatever the classes asked for**: the
  parameter then means what its confirmation says without a condition, and the
  classes restrict only what the job writes.

## The embeddings health check reads every row's view

**Status:** open (an accepted cost; a cache is the proposed fix).

`Dataset.record_embedding_health` (`src/pixano/datasets/dataset.py`) reads no
vector, but it reads the `view_id` of every row of a model's embeddings table to
count the media embedded, and counts the rows of each image table. The explorer
calls it before every semantic search, and for every model the dataset holds on
every request for its filter schema (`src/pixano/api/routers/explorer.py`) — the
media counted once for all —, so its cost grows with the number of vectors of
every model — six per record and model on a six-camera dataset.

It was accepted because counting distinct media is what makes the answer right:
counting rows said "complete" with one camera of six embedded. No measurement of
its cost on a large table is recorded.

Options:

- **Cache the answer per dataset instance**, keyed by the Lance versions of the
  embeddings and image tables, and keep the exact scan for computing and
  repairing. Beside it, `search_records` runs one vector search per vector of a
  "similar to" record and rebuilds the record-id prefilter for each: building
  that prefilter once per request is the same kind of saving.
- **Keep counts in the sidecar, updated as vectors are written.** Cheap to read,
  but a counter can drift from what it counts, and every writer of the table
  must keep it.
- **Keep the scan**, and measure it at scale first.

## Embeddings after an import: which models, and at what cost

**Status:** which models is decided (2026-11-10); the cost is open.

Since a dataset keeps one table per embeddings model, an import computes again every
model the dataset holds, as decided with that rework (2026-11-06): the media it
added are in none of their embeddings (`src/pixano/api/jobs/follow_ups.py`,
`_fit_embeddings`; data-import-export spec, amendment of 2026-11-02). How was chosen
while implementing, and decided on 2026-11-10:

- **The model the import names is computed beside the ones held; a model the
  deployment chose is not.** `PIXANO_EMBEDDINGS_MODEL`, or the first model the
  inference serves, stands in only for a dataset without embeddings: by default, an
  add import into a dataset that holds SigLIP computes SigLIP, and adds no CLIP.
- **One job per model name.** A job computes the checkpoint the inference serves
  under the name, into that checkpoint's table: a held checkpoint no longer served is
  not computed again — its table keeps lacking the new media — and the served one gets
  a table of its own.
- **A held model the inference no longer serves is queued anyway**, and refused at its
  job's planning, on every add import until its embeddings are deleted
  (`DELETE /datasets/{id}/embedding-spaces/{space_id}`). The application cannot know
  what the worker's inference serves, and the command line asks no inference.
- **An explicit request without a model to name queues nothing**, the dataset's own
  models included: `--embeddings` without `--embeddings-model` nor
  `PIXANO_EMBEDDINGS_MODEL` says so at once, as before.

The cost is the open part. Each job computes the whole dataset again, since the
embeddings job has no way to compute only what is missing: on the CPU stack measured
for step 1, about four images a second, an add import of a few images into a dataset of
10,000 holding three models runs about two hours of inference. Two add imports in a row
queue the same jobs twice: nothing checks for a job of that model still to run on the
dataset. A mode of the embeddings job that skips the media a model's table already
holds would make the recomputation cost what the import added; skipping a model whose
job is still pending would remove the duplicates.

## The overview reads whole tables at each request

**Status:** open (an accepted cost of the first version; not measured at scale).

A dataset's overview (`GET /datasets/{id}/overview`, backend-processing §22.7) reads, at
each request, the records' columns it counts, every image's size and every object's class
from their tables, and the statistics tables, then DuckDB counts them. A filter added from
a card reads them all again. It answers at once on the VOC sample (60 records, 225
objects); a dataset of a million records and ten million objects was not tried.

Options, once a dataset shows the cost:

- **Cache a reading** per dataset and table version, the filters applied on it: the tables
  change only when a job or a person writes them.
- **Count in the statistics job** what the overview reads from the tables as they are —
  an image's size per record, the classes of a record's objects — so that a request reads
  the statistics tables alone.

## The overview and its default statistics: choices made while implementing

**Status:** partly open. The user answered on 2026-11-13; each point below says whether it is
decided, open, standing for now, or changed.

The overview of statistics v1 (backend-processing §22.7) follows the plan validated on
2026-11-09 — as close as can be to Know Your Data, default statistics computed after each
import, nothing read from the pixels. These points were chosen while implementing it,
without being asked:

- **Decided.** **The overview follows the explorer's filters**, the free text and a raw
  clause included, and a card of a column filtered counts what the other filters keep (Know
  Your Data's way). A semantic search's text is ignored: the overview counts every record
  the filters keep, unranked.
- **Open, to think about.** **A card per image or per object filters nothing**: the
  explorer's filters are on the records, and "the records holding an image of 640 pixels" or
  "an object of that class" are no column of theirs. The cards of the records' own fields
  and statistics filter.
- **Changed.** **The default statistics are queued by default after every import**, where a
  worker declared the statistics job (`PIXANO_STATISTICS_AFTER_IMPORT=true`); the request
  (`compute_statistics`) and the command line (`--statistics`, `--no-statistics`) can say
  otherwise. The import form offered no box for it; it now has one, "Compute statistics
  after the import", opened on that default as the embeddings' box is
  (`GET /io/imports/statistics`).
- **Stands for now, to revisit.** **Every default statistic is computed again after an add
  import**, the whole dataset over: the statistics job has no way to compute only the
  records added. It calls no inference and measured 60 records in about a second, but a
  large dataset was not tried, and two add imports in a row queue two jobs.
- **Decided.** **A dataset with nothing to count needs no job, which is not a refusal**: the
  import says the statistics were not needed (`FollowUp.skipped`), in the tray's plain
  color.
- **Decided.** **The base `comment` field has no card**, like the identifier and the
  timestamps: it is an annotator's note on a record, not data.
- **Decided.** **An add import's rollback is refused once the statistics job has run**, as
  it already was once the embeddings job had: the statistics job writes its tables and
  `info.json`, the embeddings job its tables and `embeddings.json`, which the rollback refuses
  to undo over (data-import-export spec, amendment of 2026-11-10).
  Leaving the tables a job derives from the data out of that check would keep the rollback;
  it was not done.

## The Jobs panel opened without a dataset

**Status:** open (left as it was when the panel of a dataset was given its own jobs, 2026-11-12).

A Jobs panel opened on a dataset lists that dataset's jobs only (`jobsOfDataset`, in the new
UI's jobs store). The new UI also opens it from the dataset list, with no dataset: it then
lists every dataset's recent jobs, as it did everywhere before, and a row names only its
job's kind — nothing tells which dataset a job runs on, and its Cancel is offered all the same.
The store holds the datasets' identifiers, not their names; naming the dataset on a row, when
the panel has none, would take the list of datasets the explorer already reads.

## An entity the save queue gave up on stays in the dataset

**Status:** open (an accepted limit).

The new interface's save queue deletes an entity it created and no longer
names, and only conditionally (`DELETE …/entities/{id}?only_if_unnamed=true`):
the server deletes it only if no stored row names it. It never deletes an
entity named by a write that failed without the server refusing it — a network
error, a lost answer, a 5xx —, since that write may have been stored
(`mayHaveStored` in `ui/apps/web/src/lib/workspace/mutationQueue.svelte.ts`).
When it was not, the entity stays in the dataset, named by nothing: a draft
deleted after its create's answer was lost, a reassignment lost and then
changed. `reset()` — a Discard, another record opened — forgets the entities
the queue created as well, so one whose create had left before a Discard can
stay the same way.

It was accepted as the price of never deleting what a stored row names: the
browser sees one record, and cannot tell what a write whose answer was lost
stored. Keeping the delete queued after a Discard would show one unsaved item
right after it. FRONTEND_ARCHITECTURE.md describes the queue's rules.

Options:

- **A server-side sweep** of the entities nothing names, as a maintenance
  command or a job.
- **Read the record back after a failure that is not a refusal**, before
  deciding what the queue still owns. It would also close the other cases of a
  lost answer, where the server stored a write the browser takes for failed.
- **An identifier per write**, so that a retry can ask whether a write landed.

## A chunk's weight multiplies the worker's time limit

**Status:** open (chosen while implementing, not decided).

The review decided that a chunk's time limit follows its work, through a weight
its kind declares at planning (backend-processing §9). How the weight turns
into a limit was left open. A kind now weighs a chunk in inference calls, and
the worker gives it that many times `PIXANO_WORKER_CHUNK_TIMEOUT_S`, which stays
the limit of a chunk of one call (`Chunk.weight` in
`packages/pixano-worker/src/pixano_worker/kinds/base.py`, `_execute` in
`runner.py`). The setting then binds every call a weighed chunk makes: a
deployment that lowers it to fit its fast kinds sends back long chunks the
inference server would still have answered, and the kind cannot say so.

Options:

- **The weight multiplies the deployment's limit**, as today: a slower
  deployment raises one number for every kind, and a kind says nothing of
  durations.
- **The kind gives the chunk a duration of its own**, computed from its own
  timeouts: exact for each kind, but out of the deployment's hands, and every
  kind must know its worst case.

## Tracking boxes: choices made while implementing

**Status:** open (chosen while implementing the boxes the tracking job proposes, 2026-11-19).

The user decided on 2026-11-19 that the tracking job proposes boxes as an option of the job —
masks, boxes or both —, masks by default, so that nothing changes without it
(backend-processing §23.3). These were chosen while implementing it, without being asked:

- **The parameter is `output`, its values `masks`, `boxes` and `both`**, a closed list of strings
  rather than an enumeration, whose choices the forms read where the parameter stands without
  depending on the change that inlines an enumeration's choices.
- **Each table protects a person's work on its own**: a person's box keeps the model's box off its
  frame, a person's mask the model's mask, as for masks before boxes. A person's mask does not
  keep the model's box off its frame, nor a person's box the model's mask; the other choice would
  change what a job asked for masks writes, which the decision rules out.
- **A job replaces only what it was asked for**: a job asked for boxes leaves the masks an earlier
  one proposed, and the other way round. The other choice — a job replaces the model's masks and
  boxes after its keyframe, whatever it proposes in their place — would keep a video from holding
  boxes of one track and masks of another, at the cost of deleting proposals nobody asked to
  delete.
- **The tracklet counts every mask that names it, and only the boxes the job wrote**: a box a
  person drew, which the legacy workspace joins to a tracklet whose span it falls in, is left out,
  as a job asked for masks always left it. Counting it would keep the tracklet over every
  person's box joined to it, at the cost of changing what a job asked for masks writes.
- **An object deleted loses the model's masks and boxes alike**, whatever the job was asked for:
  nothing will track it again to clean what the other output left.
- **A box carries no score** (`confidence` -1): SAM 2's video predictor answers none.
