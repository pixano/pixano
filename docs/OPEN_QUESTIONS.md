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
