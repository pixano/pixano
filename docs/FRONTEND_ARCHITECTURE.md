<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

# Frontend Architecture & Data Flow — `ui/apps/web`

How the next-UI annotation frontend is wired end to end: from the LanceDB tables
on disk, through the FastAPI backend and the REST gateway, into the reactive
workspace, and out to the widgets / tools / renderers the user interacts with.

> Companion docs:
> - [`ARCHITECTURE_TOOLING.md`](./ARCHITECTURE_TOOLING.md) — the *why* (design
>   decisions D1–D10, the plugin model, known debts).
> - This file — the *how it connects* (the layers, the contracts, the flows).

---

## 1. The big picture

```
┌──────────────────────────────────────────────────────────────────────────┐
│ BACKEND  (src/pixano)                                                      │
│                                                                            │
│  LanceDB tables ── grouped by SchemaGroup ──┐                              │
│   records | entities | bboxes | bbox3ds |   │                             │
│   masks | keypoints | …                     │                             │
│                                             ▼                             │
│  Dataset (datasets/dataset.py)  ──►  BaseService (api/service.py)          │
│     get_data / add_data / update_data / delete_data / open_table          │
│                                             ▲                             │
│  create_resource_router (api/routers/resources.py) ── one generic CRUD    │
│     router per ResourceSpec  →  GET/POST/PUT/DELETE /datasets/{id}/{res}   │
└──────────────────────────────────────────────────────────────────────────┘
                         ▲   REST/JSON   │
                         │               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ FRONTEND  (ui/apps/web/src/lib)                                            │
│                                                                            │
│  api/annotations.ts  ── thin fetch() wrappers (one per endpoint)          │
│        ▲                                                                   │
│  DatasetGateway (workspace/datasetGateway.ts)  ── the seam tools/queue    │
│        │                                          depend on (not fetch)    │
│   ┌────┴───────────────── WorkspaceManager ─────────────────────────┐     │
│   │  owns: WidgetRegistry · WorkspaceSession · RecordLoader ·        │     │
│   │        MutationQueue · widgets[] · storageMap · pendingAnnotation │    │
│   └───────────────┬───────────────────────────────┬─────────────────┘     │
│                   │ record-scoped shared state     │ per-widget            │
│                   ▼                                ▼                       │
│        WorkspaceSession                       Widgets (hosts)              │
│         · annotations: AnnotationCollection    ImageWidget (Konva)         │
│         · entities / schema                    PointCloudWidget (Threlte)  │
│         · visibleEntityIds                          │                      │
│         · hiddenReviewStatuses (review filter)      │                      │
│                   │                                 │ builds a             │
│                   │ read/write via                  ▼ Scene2DContext       │
│                   ▼                            Tools (input)               │
│         ViewScopedAnnotations  ◄──────────────  Renderers (display)        │
│           (per-widget facade)                                              │
└──────────────────────────────────────────────────────────────────────────┘
```

Three ideas hold it together:

1. **One shared, record-scoped annotation model** (`AnnotationCollection`) that
   every widget viewing the same record reads and writes — moving a 3D box updates
   its 2D projection because both read the same object.
2. **Per-kind plugin registries** (tools, renderers, payload builders, seed
   loaders) so a new annotation kind is added by dropping a module + registering
   it, never by editing a widget or the queue.
3. **Narrow boundary interfaces** (`DatasetGateway`, `Scene2DContext`,
   `MutationSink`, `AnnotationStore`) so tools/renderers/queue depend on contracts,
   never on the concrete `WorkspaceManager`.

---

## 2. Backend slice (what the frontend talks to)

### Storage — `src/pixano/datasets`
- **LanceDB** tables hold the rows; **DuckDB** is used for analytics. Media is
  served separately via `MEDIA_DIR`.
- Tables are organised into **`SchemaGroup`s**: `RECORD`, `VIEW`, `ENTITY`,
  `ANNOTATION`, `ENTITY_DYNAMIC_STATE`, `EMBEDDING`, `TIMESERIES`.
  `dataset.info.groups.get(group)` returns every table in a group — this is how the backend sweeps "all annotation
  tables" or "all entity tables" without hard-coding kinds.
- A row's `entity_id` is the foreign key from an annotation to its entity.

### Generic CRUD — `src/pixano/api`
- **`ResourceSpec`** (`api/resources.py`) declares one resource: `name`, `path`,
  `schema_group`, `schema_cls`, `validate_create`, `allow_*`. Every kind (bbox,
  bbox3d, mask, keypoints…), plus `entity`/`record`/`view`, is a `ResourceSpec`.
- **`create_resource_router(spec)`** (`api/routers/resources.py`) builds one CRUD
  router per spec → `GET/POST/PUT/DELETE /datasets/{dataset_id}/{path}[/{id}]`.
- **`BaseService`** (`api/service.py`) is the shared CRUD logic:
  - `list/get/create/update/delete` over the resolved table;
  - FK validation on **create and update** (`validate_entity_exists`) so an
    annotation can't point at a missing entity;
  - **orphan-entity cascade** (opt-in `?prune_orphan_entity=true`): on an
    annotation's delete, or an update that changes its `entity_id`, the entity it
    named is removed from its `ENTITY` table (`_delete_orphan_entity`) once no
    stored row names it — the conditional delete's check below
    (`_entity_is_named`): an annotation of any table, a child entity, an entity
    dynamic state. One mechanism, every kind, server-side (the only place that
    sees every reference — the frontend loads one record at a time). The write,
    the check and the entity's delete hold the request's one write lock, so no
    write naming the entity lands between the check and the delete: one arriving
    meanwhile is refused as a busy dataset's 409. An entity that only a child
    entity, a dynamic state, a message's `entity_ids` or a relation's end still
    names stays once its last annotation is deleted or moved.
  - **conditional entity delete** (`?only_if_unnamed=true`, on every `ENTITY`
    resource — `_add_entity_delete_route`): `delete_if_unnamed(id)` deletes the
    entity only when no stored row names it — an annotation of any table, by
    `entity_id`, `entity_ids` or a relation's `subject_id` / `object_id`; an
    entity, by `parent_id`; an entity dynamic state, by `entity_id`
    (`_entity_is_named` over `_ENTITY_REFERENCES`, each table asked only about
    the columns it has). It answers 200 `{"deleted": true | false}`
    (`ConditionalDeleteResponse`) — false: something names it, nothing changed
    — and 404 when there is no such entity. The check and the delete hold one
    dataset write lock, so no write naming the entity lands between them: one
    arriving meanwhile is refused as a busy dataset's 409. Without the
    parameter, an entity's `DELETE` is unchanged: deleted whatever names it,
    answered 204.
  - **review rules** on every entity annotation's update and create
    (`api/review.py`): a person's saved edit of a model's row accepts it and
    keeps the model's provenance and score (each schema declares its own score
    fields — a box's `confidence`, a classification's `confidences` — and a list
    of scores follows the labels it scores when a person changes them); the one
    decision (`review_status`) is `accepted`, and any other value but an echo or
    `pending` is answered 400; a person's row takes no status. Rejecting a
    model's row is its delete. A person's edit of an entity — its class, say —
    accepts the model's pending annotations that name it, whatever their kind.
    One rule set, every kind — see `docs/specs/backend-processing.md` §19.
  - a `PUT` whose body names another row (an `id` other than the path's) is
    answered 400 before anything else, for every resource.

### REST surface the frontend uses
| Function | Defined in | HTTP | Notes |
|---|---|---|---|
| `getDataset` | `api/datasets.ts` | `GET /datasets/{id}` | schema + views |
| `listEntities` | `api/annotations.ts` | `GET …/entities?record_id=` | record-scoped entity rows |
| `listAnnotations<TRow>` | `api/annotations.ts` | `GET …/{resource}?record_id=` | **kind-generic** — the caller passes the `resource` its payload builder owns, so a new kind adds no method here |
| `loadImageByLogicalName` / `loadPointCloudByLogicalName` | `api/workspace.ts` | `GET …/{view}` | media + calibration |
| `createEntity` | `api/annotations.ts` | `POST …/entities` | |
| `deleteEntity` | `api/annotations.ts` | `DELETE …/entities/{id}` | a 404 counts as done, any other failure throws an `ApiError` with its status |
| `createAnnotation` | `api/annotations.ts` | `POST …/{resource}` | kind-generic (resource = table) |
| `updateAnnotation` | `api/annotations.ts` | `PUT …/{resource}/{id}?prune_orphan_entity=true` | geometry / entity reassign |
| `deleteAnnotation` | `api/annotations.ts` | `DELETE …/{resource}/{id}?prune_orphan_entity=true` | also a model's annotation's Reject (§8); a 404 counts as done, any other failure throws an `ApiError` with its status |

Note `listAnnotations`' `view_name` query parameter actually filters the `view_id`
column for annotations (legacy server-side naming — see `service.list` in
`src/pixano/api/service.py`).

---

## 3. The DatasetGateway — the I/O seam

`workspace/datasetGateway.ts` defines **`RecordReadGateway`** (reads) and the full
**`DatasetGateway`** (reads + `createEntity`, `deleteEntity`, `createAnnotation`,
`updateAnnotation`, `deleteAnnotation`). The default `httpDatasetGateway` forwards
to `api/annotations.ts`.

Why it exists: the `MutationQueue` and `RecordLoader` depend on this **interface**,
not on `fetch`. Tests pass an in-memory fake; nothing else changes. The frontend
never calls `fetch` outside `api/`.

The writes (`MutationGateway`, the half the queue sees) keep one contract on
failure: a write the server refused — a 4xx — rejects with an `ApiError`
carrying that status (`isRefusal`, `api/apiClient.ts`), a delete as any other,
and stored nothing; any other failure — a network error, a lost answer, a 5xx —
may come after the write was stored.

---

## 4. The workspace orchestration layer

### `WorkspaceManager` (`workspace/workspaceManager.svelte.ts`)
The single object Svelte components hold. It does not *contain* the logic — it
**composes** the sub-services and exposes a flat API:

```
WorkspaceManager
 ├─ registry   : WidgetRegistry          // which widget kinds exist
 ├─ session    : WorkspaceSession         // record-scoped shared state
 ├─ mutations  : MutationQueue            // pending → backend
 ├─ loader     : RecordLoader             // (dataset, record) → widgets + data
 ├─ widgets[]  : WidgetInstance[]         // the laid-out widget set
 ├─ storageMap : per-widget storage       // e.g. activeToolId (NOT annotations)
 ├─ pendingAnnotation                     // box awaiting its entity choice
 └─ review     : ReviewController         // list, status chips, decisions (§8)
```

Representative API: `openRecord` (the way to switch records, or to open the
same one again: clears the workspace, unsaved changes included, then
`selectRecordInDataset`), `flushSave`, `discardChanges`, `queueMutation`,
`upsertUpdateMutation`, `deleteAnnotation`, `beginPendingAnnotation` /
`confirmPendingAnnotation` / `cancelPendingAnnotation`, `isEntityVisible` /
`toggleEntityVisible` / `showAllEntities`, `isShownByReview` (the review status
chips, read through `review.isShown`, §8), `claimStagedWork` /
`releaseStagedWork` (a flag per holder of work a tool keeps unconfirmed, reached
through the seam — "Unsaved work and saves" below), `discardStagedWork(widgetId)`
(one widget's share of Discard, which a delete pressed mid-gesture calls first —
flow E), `unsavedCount` (how many items of the record are unsaved, the one count
every unsaved counter shows — "Unsaved work and saves" below), `hasUnsavedWork`
(that count is not 0),
`saveDatasetLayout` / `restoreOpeningLayout` / `fitLayoutToViewport`. Getters
forward to the session/queue (`annotations`, `entities`, `pendingCount` — the
request on the wire included — `pendingMutations` — the queued ones only —
`saving`, …).

`flushSave()` resolves to a boolean: true when the save went through **and**
nothing is left unsaved — `unsavedCount` is 0: no queued change, no request on
the wire, no draft, no entity form open, no work a tool holds staged. It is
false when the save failed (the error is on `saveError`), when another save was
still running, when work begun during the save or held in a tool is still
unsaved, or when another record was opened while it ran: that record's state is
not this save's to read back or report on, so nothing is read back then. On the
record it saved, a save that sent something reads the record back (`readBack`:
the entities, then the annotations, merged with the work done meanwhile — flow
D); one that failed reads back its entities only, since a write before the
failure may have created one.

**Per-dataset layout preference.** Every record of a dataset declares the same
views, so the arrangement the user builds on one is replayed on the others
(`workspace/datasetLayout.ts` for the rules, `datasetLayoutRepository.ts` for
storage). Widgets are keyed by `viewName` — the only identifier that survives a
record switch. Three invariants hold this together:

- **Only gestures persist.** The grid also writes layouts back when *it* places
  widgets (mount, clamping, compaction after a hide); persisting those would
  freeze an automatic placement, computed for one record's widget count, as if
  the user had chosen it. `GridWorkspace` calls `saveDatasetLayout()` at the
  points where an arrangement has settled after a user action, and nowhere else.
- **A position is never stored before the grid has resolved it.** Hiding compacts
  the neighbours and showing re-places a widget wherever a slot is now free, so
  the save waits for GridStack to react (behind the deferred mount's microtask
  for a show). The one deliberate exception is a fully hidden workspace, which is
  never written at all — see `snapshotDatasetLayout`.
- **A programmatic arrangement is authoritative.** `restoreOpeningLayout` /
  `fitLayoutToViewport` decide every position themselves, so the reconciliation
  effect skips the gap-fill meant for a user hide while applying one; otherwise
  compaction would overwrite the very positions being restored.

`layoutRevision` is the reverse channel: bumped when the manager rewrites layouts
itself, it tells `GridWorkspace` to push the new positions — and their lowered
`minW`/`minH` — into GridStack. It is watched *alone*: depending on the layouts
themselves would re-run that effect mid-drag and fight the user's gesture.

**The workspace lock covers every control that can move a widget.** `editMode`
off puts GridStack in static mode, and the inspector disables the layout actions
*and* the per-widget visibility toggles alongside it. Visibility belongs in that
set rather than being display-only: hiding a widget compacts its neighbours and
the grid stores the result, so an ungated toggle would write the very arrangement
the lock exists to protect.

See `docs/OPEN_QUESTIONS.md` for the limitations accepted in this first version.

### `WorkspaceSession` (`workspace/workspaceSession.svelte.ts`)
The record-scoped truth, replaced on every load:
```
datasetId · recordId · entities[] · entitySchemaName · entitySchemaFields
annotations : AnnotationCollection      // the shared model (§5)
visibleEntityIds : Set<string> | null   // entity-driven visibility (null = all)
hiddenReviewStatuses : ReadonlySet<ReviewFilterKey>  // review chips switched off
stagedWork : ReadonlyMap<string, StagedWorkHolder>  // raised staged-work flags
```
Held on a tiny shared object so each sub-service depends on this narrow type, not
on the whole manager. `isEntityVisible(entityId)` reads `visibleEntityIds`; the
manager and the `ReviewController` both ask it, so the review list holds only the
annotations of the entities the Entities tab shows.

`stagedWork` shows the raised flags of work no mutation carries yet — a
polygon's points before Enter, a box being resized, a shape being dragged —
each with its widget and the callback that drops the work. Each holder raises
and lowers its own flag through its widget's seam (`claimStagedWork`, "Unsaved
work and saves" below); while any is raised the record is not all saved, and
each raised flag counts as one unsaved item (`unsavedCount`). The manager alone
writes the flags, in a private map it publishes here as a copy — always
replaced, never mutated, like `hiddenReviewStatuses` — and `clearWorkspace` /
`reset()` empty it with the widgets.

`hiddenReviewStatuses` is the one exception to "replaced on every load": it is
a reviewer's preference, not a property of the record, so neither a load nor
`reset()` touches it and the next record opens with the filter the reviewer
works with. It defaults to empty — nothing hidden — and a chip toggle
(`ReviewController.toggle`) **assigns** a new `Set`: Svelte 5 does not track a `Set`'s `add`/`delete` (the same pattern
as `visibleEntityIds`).

### `RecordLoader` (`workspace/recordLoader.ts`)
`load(datasetId, recordId, viewport)`:
1. Set `session.datasetId/recordId`; reset `entities`, `annotations`,
   `visibleEntityIds`. A `loadToken` guards every async write so a fast
   record-switch can't let a stale fetch overwrite the new record.
2. In parallel: `getDataset` + `listEntities`.
3. For each declared view, ask each registered **extension** `addRecordSeed(...)`;
   run the per-kind **`SEED_LOADERS`** to fetch that record's annotation rows and
   map them into the shared `AnnotationCollection`. They run through
   `loadEveryKind` (`seedLoaders.ts`), which keeps each failure to its kind: a
   kind whose rows could not be read seeds nothing, is reported on the console,
   and the other kinds are read.
4. Create one widget per claimed view, keyed by `viewName`. Placement comes from
   `resolveRecordLayouts`: the dataset's remembered arrangement where the user
   has arranged that view, `layoutPlanner`'s automatic placement otherwise. The
   resolved state is kept on `session.openingLayout` so "Reset layout" can undo
   the moves made on this record.

`reloadEntities(stillWanted?)` refetches just the entity list so the
panel/picker reflect created/pruned entities: after a save, and by Discard
before its rows. It is token-guarded, and `stillWanted` is asked once the list
has arrived, as for the annotations: a read-back calls it off when a write has
landed since it began — the list may predate that write, and would take its
entities off the panel and the labels of the boxes moved onto them.

`reloadAnnotations({stillWanted?, holdsWork?})` refetches the annotations
through the seed loaders and merges them into the collection, without touching
the widgets, their arrangement or their tools. Both read-backs use it — a save's
and Discard's, each through `WorkspaceManager.readBack`, right after
`reloadEntities`: each annotation's label snapshot is read from the entities, so
the other order labels a reassigned box with nothing. The rows never overwrite
work done while they were read (`AnnotationCollection.takeRowsRead`, §5): an
annotation `holdsWork` names — a write of it queued or on the wire — keeps its
version here, drafts stay, an annotation deleted here stays deleted, and every
other annotation becomes its row, in place, so a tool or an editor in the middle
of a gesture commits by id onto the row read. Only the kinds actually read are
replaced: a kind whose list failed keeps every annotation it shows, and the
failure is reported. A failed request says nothing about what the dataset holds;
taken for an empty table, it would take the whole kind off the canvases and the
chip counts after one 5xx, while the save said it had succeeded. It is
token-guarded like the others, and `stillWanted` is asked once the rows have
arrived, before they are taken: the read-back passes "no write has landed since
I began" (`MutationQueue.writesLanded`, below), since rows read before a write
that landed may predate it — that write's own save reads the record back. Two
more guards keep a read-back from landing where it does not belong:

- **Not while another record loads.** The loader records which record its views
  were read for (`viewsRecord`); a reload asked between a load's start and its
  views reads nothing, since the rows would be placed against the previous
  record's views. A load also checks its token before recording its views, so
  of two loads the later one's views win.
- **Never older rows over newer ones.** Each reload takes a number as it starts
  (`reloadCount`), and the loader keeps the number of the latest one whose rows
  were taken (`latestLanded`): rows read before rows already taken are dropped,
  whatever order the answers arrive in. A later reload that never lands — called
  off, or failed for every kind — does not stop an earlier one that still applies.

### `MutationQueue` (`workspace/mutationQueue.svelte.ts`)
Owns the list of pending writes and the flush lifecycle. Implements **`MutationSink`**:
`queue`, `upsertUpdate` (replace the last queued update for the same
resource+id, taking the newer gesture's `widgetId` with its body),
`patchPendingCreate` (merge into a not-yet-sent create), `dropForLocalAnnotation`.
Plus reactive `pending`, `inFlight`, `count`, `saving`, `saveError`, the plain
counter `writesLanded`, and `holdsWorkFor(id)` (a write of that annotation queued
or on the wire). `writesLanded` counts the writes that reached the backend: each
one answered, and each one that failed without the server refusing it — after a
network error, a lost answer or a 5xx it may have been stored. A refusal (a 4xx,
`isRefusal` — a delete as any write, §3) stored nothing, and is not counted. A
read-back begun before the count last moved is called off (`RecordLoader`
above). Each time
a body is written into the queue — queued, or rewritten by a later gesture — the
**`LocalAnnotationLocator`**'s `recordQueued(mutation)` is told, so the manager
keeps the content that body carries (`AnnotationCollection.contentOf`) until it
leaves.

**A request on the wire is out of reach.** A mutation leaves `pending` as its
request leaves and is `inFlight` until the backend answers; `count` includes it.
Nothing queued meanwhile can be written into a body the server already has —
which would drop that work unsent once the request returned:

- an edit on that row is queued after it, as an update of its own;
- `patchPendingCreate` on a create already on the wire queues an update of the
  row it makes (the local annotation id doubles as the row id); should that
  create fail, it comes back ahead of the update, and a later patch goes into
  the update, sent last;
- `dropForLocalAnnotation` on a create already on the wire queues a delete of
  that row, so a draft dropped during its save does not stay in the dataset. That
  create is _abandoned_: should it fail, it is not tried again. Should the server
  refuse it (a 4xx), it made nothing: the delete is dropped, and no failure is
  reported. Should it fail any other way — a network error, a lost answer, a
  5xx — it may have made the row: the delete stays queued, and the failure is
  reported. A delete answered 404 counts as done (`api/annotations.ts`), so that
  delete costs nothing when the row was never made. Only a reset of the queue
  (Discard, another record) before that delete is sent leaves the row there.

A failed request goes back to the head of the queue, and `upsertUpdate`
replacing the last queued update keeps the gestures in their order behind it:
an edit made after a failed save is the one sent last.
`reset()` (another record opened, Discard) bumps a generation: a request still in
flight then neither comes back into the new queue nor reports its error there.

`flush()`:
1. `sortMutations(pending)` by **`mutationPriority`**: `entityCreate(0) <
   annotationCreate(1) < annotationDelete(2) < entityDelete(3)` — entities are
   created before the annotations that reference them, and deleted after them.
2. POST/PUT/DELETE each via the gateway, through `sendIfStillQueued`. Every
   request is awaited, and a gesture made meanwhile may drop a write this flush
   is about to send (a draft deleted, a change of mind), rewrite it to name a
   new entity whose create was queued after the flush began, or reset the queue
   (Discard, another record). So each write is looked at again after every
   await: one no longer queued, or whose queue was reset, is not sent; one
   naming an entity whose create is still queued — by its `entity_id` as it
   reads now — waits for that create to be sent, and is looked at again, until
   no such create is left. No write names an entity that does not exist yet,
   and none dropped while the flush ran is sent. As each request leaves, the
   locator's `recordWrite(mutation)` records what the dataset will hold once it
   lands (§5, `AnnotationCollection.recordWrite`): the content the body carried
   when it was queued; a failure undoes that record. As it completes,
   `writesLanded` is bumped, unless the server refused it.
3. On a successful **create** of an annotation, flip its local `persisted = true`
   via the locator's `findLocalAnnotation(id)` (→ the session's
   collection). Drafts thus become "saved" without a per-widget lookup.

A flush that finds the queue empty clears `saveError`: what failed is no longer
queued (a draft whose create failed, then deleted), so nothing is left to report.

### Unsaved work and saves

**A save never loses work begun during it.** The queue never writes into a
request already on the wire, and a failed request returns to the head of the
queue (§4, `MutationQueue`). A write dropped while a save runs — a draft
deleted, a change of mind, Discard, another record — is never sent, since each
write is looked at again after every await of the flush; a write a gesture
moved onto a new entity during a save waits for that entity's create, sent
first, whenever it was queued. A read-back never lands on another record, nor
over newer rows: `flushSave` checks the open record before and after it, rows
read before a write that landed since are dropped — `writesLanded`, which a
refused write leaves as it is, so a failed later save that stored nothing calls
off nobody's read-back — and rows read before rows already taken are dropped,
while a later read that never lands stops nothing (§4, `RecordLoader`). Nor does
it land over work: its rows merge with what was done while they were read —
queued or on the wire, drafts, deletes — and a shape a gesture holds commits
onto the row read (`takeRowsRead`). A save's entity list is read back under the
same guards, before its annotations, so the two go together; a save that failed
reads back its entities only. Discard puts the stored record back at once, then
reads it again by the same path, entities before rows, so its labels follow the
dataset: an edit or an Accept made while the rows are read stays, on screen and
in the queue, and a write that lands meanwhile calls the read off.

**Staged work.** Work a tool holds outside the queue, waiting for the person to
confirm it, is unsaved work too: a polygon's or polyline's points before Enter,
mask strokes, keypoints partly placed, smart segmentation's prompts, a box being
drawn, a box being resized, a shape being dragged. Each holder claims a flag of
its own once, through its widget's seam, with the callback that drops its work
(`SceneContextBase.claimStagedWork(discard)` → `manager.claimStagedWork`,
stamped with the widget's id and keyed to the holder, so lowering one flag never
lowers another, in this widget or another), and raises it while it holds the
work. The 2D tools raise theirs from the first point, stroke or press, and lower
it on commit, Escape, `deactivate` and an undo that empties it (the contract on
`ToolHandler2D`, `scene/tool.ts`).

A 2D editor holds its flag while a gesture on a stored shape runs, raised as the
gesture starts and lowered as it ends, never at each pointer move. The bbox
editor holds it from `transformstart` to `transformend`, keeping the transformer
on the box it resizes whatever the selection does. The bbox, mask, multi-path
and keypoints editors hold it from a shape's `dragstart` to its `dragend`, the
whole shape or one of its points — for multi-path and keypoints, the shared
`scene/flatCoordsEditor2D.ts`, which holds the drag for every kind on it, each
naming only its attribute in its spec. The editor stamps the node it holds (the
path's or the skeleton's group when a point is dragged) with its kind's
attribute — `BBOX_RESIZING_ATTR`, `BBOX_DRAGGING_ATTR`, `MASK_DRAGGING_ATTR`,
`MULTI_PATH_DRAGGING_ATTR`, `KEYPOINTS_DRAGGING_ATTR` — and the renderer's sync
leaves a stamped node alone, so a save ending under the gesture neither snaps
the shape back nor drops its move: its read-back takes the shape's row into the
collection, in place, the node stays where the gesture has it, and the gesture
is committed by id onto that row when the pointer is let go — only one the
editor saw begin.

A delete pressed during the gesture cancels it first (flow E), so the delete —
a Reject, on a model's shape — applies to the shape as stored.

A widget lowers its holders' flags as it closes (`releaseStagedWork`), since
nothing in it can confirm that work any more. While a flag is raised, a save
that sent something reads the record back as any does — the entities, then the
rows, merged with the work queued, the held shape left where the gesture has it
— and reports work left: `flushSave` resolves false. Each raised flag counts as
one item of `unsavedCount`, so the counters never read 0 while a tool holds
work. Discard calls every raised flag's discard — a tool forgets its points, a
resize or a drag stops and commits nothing, and each annotation shows as stored
— and is offered whenever anything is
unsaved (`manager.hasUnsavedWork`: the toolbar's `discardDisabled`), even with
nothing queued. The manager keeps the raised flags in a private map and
publishes a copy on `session.stagedWork`: widgets lower their flags from effect
teardowns, where Svelte gives a reactive read the value it had before the
latest writes, so a change computed from the session there could bring a flag
back or drop one another widget had just raised.

**One unsaved count.** `WorkspaceManager.unsavedCount` is the only count of the
record's unsaved work, derived once for every widget toolbar and `flushSave`,
so they never disagree. Its rule is `countUnsavedWork`
(`workspace/unsavedWork.ts`), over the changes queued and the one on the wire:
an annotation counts once, whatever they hold for it — an edit, a new entity and
the update naming it — and so does a draft; a change that names no annotation
counts on its own; an open entity form counts once — a draft's form is its
draft, already counted, so only a stored annotation's reassignment adds one; and
each raised staged-work flag counts once. `hasUnsavedWork` is that count above
0, and it is what `flushSave` reads. The rule takes a draft no queued change
names for the draft the open form belongs to, since a draft's create is queued
once its entity is chosen; nothing on the draft says which form is its.

### Keyboard

**Keys typed in a form field stay there.** Tool shortcuts are heard on `window`.
Every listener there — the image widget's, the 3D box editor's — asks
`isFormFieldTarget(event.target)` (`scene/tool.ts`) first: a text field types
the key, and a select picks an option with it instead of starting a
reassignment on `E` or deleting the selection on Backspace.

---

## 5. The shared annotation model

### `LocalAnnotation<G>` (`annotations/annotationCollection.svelte.ts`)
The one in-memory shape for **every** kind — pure data, no methods:
```ts
{ id, entityId, kind, viewId, geometry: G, persisted, entity?, review?,
  persistedContent? }
```
- `kind ∈ AnnotationKind` (`"bbox" | "bbox3d" | "mask" | "keypoints" |
  "multi_path" | "classification"`).
- `geometry` is typed per kind via `GeometryByKind` (`bbox` → `[x,y,w,h]` norm;
  `bbox3d` → `{coords, format, rotation}` in Lance space; each other kind's shape
  is declared in its own `kinds/<2d|3d>/<kind>/<kind>Types.ts`).
- `persisted=false` ⇒ a **draft** (drawn but not yet POSTed). `entity` is a snapshot
  of the parent entity's fields so labels render without a refetch.
- `review` (`AnnotationReview`, `annotations/reviewStatus.ts`) is the row's
  provenance and review status — status, source type and name, model and version
  from `source_metadata`, score. Read once, leniently, by the shared envelope
  every seed loader builds through (`persistedAnnotation`, §8); absent on a draft,
  which is a person's work with nothing to review. It carries two statuses:
  `status`, what the screen shows, an unsaved Accept included — an unsaved
  edit leaves it as stored —, and `storedStatus`, what the dataset holds: what
  Discard puts back, and what tells an unsaved Accept (§8).
- `persistedContent` is a detached copy of what the dataset holds of the
  content — `{geometry, entityId, entity}` — set by the envelope. An edit
  overwrites `geometry`/`entityId`/`entity` in place; this copy is what the
  content was before it, and what Discard puts back. Absent on a draft no write
  has carried yet.

### `AnnotationCollection` — the record-scoped source of truth
`$state` list + `selectedId`, with `find/byKind/add/remove/select/setGeometry/
setEntity/setReview/contentOf/recordWrite/restoreStored/takeRowsRead`. **Owned
by `WorkspaceSession`, one instance per record load, shared by every widget.**
Optimistic edits mutate `geometry` (or `review`, for an Accept) in place; the
`MutationQueue` is the ledger of what still has to reach the backend.

`setReview` shows a new review state and keeps the stored status as it was: an
Accept still unsaved is never mistaken for one the server holds.
`recordWrite(id, {content?, updateBody?})` is called by the queue as a write of
the annotation leaves (through the locator). It records as `persistedContent`
the content that write carries — taken by `contentOf` when its body was written
into the queue (`recordQueued`, §4), not the annotation's content as it leaves:
a write retried after a failure leaves with newer edits queued behind it, which
it does not carry. For an update it records the status the server will store
for that body as `storedStatus` (`storedStatusAfterWrite`, the mirror of the
server's rules: `accepted` asked stores `accepted`, and so does content on a
model's row; an echo or `pending` stores nothing new). The status shown moves
with the stored one when it showed the stored one — no unsaved Accept —, so an
edited model's row reads `accepted` as its write leaves, without waiting for the
save's read-back, and is not offered Accept again — even when that read-back is
called off. A write that carries no content — an
Accept alone (`carriesContent`) — leaves `persistedContent` as it was. Recorded
as the write leaves rather than when it lands, so that work begun while it is
on the wire is measured against what the dataset will hold once it lands: an
edit taken back to the content on the wire sends nothing. It returns the undo
the queue runs if the request fails: the stored status as it was, and the
status shown when it moved and nothing has moved it since — an unsaved Accept
still shows, and is sent again with the write.

`restoreStored()` puts every annotation back as the dataset holds it — content
from `persistedContent`, status from `storedStatus` — and drops the drafts and
the selection: what Discard shows at once, before the rows are read again.
`takeRowsRead(rows, holdsWork, kindsRead)` is how a read-back — a save's or
Discard's — lands (§4, `RecordLoader`): the rows read, except where work was done
meanwhile. An annotation with a write queued or on the wire keeps its version
here, drafts stay, an annotation deleted here stays deleted, an annotation of a
kind whose rows could not be read (not in `kindsRead`) stays as shown, the
selection stays while its annotation exists, and every other annotation becomes
its row. It works in place, so the collection every widget holds stays the same
object: a tool or an editor in the middle of a gesture — work staged, in no
mutation yet — keeps working on it, and commits by id onto the row read.

### `ViewScopedAnnotations` — the per-widget facade
Implements the same **`AnnotationStore`** interface but scopes reads to *one view*,
then filters what the widget displays:
- **The view rule**:
  `_inView(a) = a.viewId === thisView || RECORD_SCOPED_KINDS.has(a.kind)`.
  `RECORD_SCOPED_KINDS = {bbox3d}` ⇒ a 3D box passes every view filter, which is
  what lets an image widget **project** it.
- **The display filter**: an `isShown(a)` predicate given at construction —
  `buildSeam` passes `manager.isShownByReview`, the review status chips (§8);
  drafts always pass it.
- The **display reads** — `items`, `byKind`, `count` **and** `selected`/
  `selectedId` — honour both. A selection on an annotation this widget does not
  show reads as no selection, so a widget's delete never acts on something it
  does not display.
- **`find` honours the view rule only, never the display filter.** It is the
  lifecycle's lookup — commit an edit, flip `persisted`, a HUD saving the box it
  holds — and a row hidden from view is still a row: an edit already under way on
  it must still reach the queue. Drafts and save are never filtered either.
- **Writes pass straight through** to the shared collection, so every other widget
  sees them immediately.

```
WorkspaceSession.annotations  (record: all kinds, all views)
        ▲ writes                         ▲ reads (scoped, then display-filtered)
        │                                │
  ImageWidget A ──── ViewScopedAnnotations(view A) ────┐
  ImageWidget B ──── ViewScopedAnnotations(view B) ────┤ same underlying collection;
  PointCloudWidget ─ ViewScopedAnnotations(its view) ──┘ bbox3d passes every view
```

Every widget builds its facade the same way, through `buildSeam` — the point
cloud included: its renderer pulls `ctx.collection.byKind("bbox3d")` from the
facade, so the review status filter applies to the 3D view like any other.

---

## 6. The annotation plugin layer (per kind)

The annotation tooling is a plugin system: per-kind **payload builders + seed
loaders** (store), **renderers** (display), and **tools/editors** (input), each
registered in a flat list (`PAYLOAD_BUILDERS`, `SEED_LOADERS`,
`RENDERER_FACTORIES_2D/3D`, `TOOLS_2D/3D`) under `annotations/scene/`. A kind lives
entirely under `annotations/kinds/<2d|3d>/<kind>/`; adding one is a folder + registry
lines, with no widget, scene, or queue edits.

- **Widgets are hosts** (`ImageWidget`, `PointCloudWidget`): scene setup, toolbar from
  the registry, event delegation. They build the medium-agnostic seam (`buildSeam`)
  and name no kind.
- **Renderers display** (they receive a *read-only* context and cannot write);
  **tools/editors handle input** (full context; they commit via
  `commitNewAnnotation` / `commitGeometryEdit`). Display and input are separate
  objects — decision **D4**.

> For the full plugin design — the `scene/` contracts (`SceneContextBase`,
> `Scene2DReadContext` / `Scene2DContext` / `Scene3DContext`, the 2D renderer/editor
> split, the 3D `overlay` / `session` / `hud`), the decisions, and the "add a kind"
> recipe — see **`ARCHITECTURE_TOOLING.md`**. This section deliberately does not
> duplicate it.

---

## 7. End-to-end flows

### A) Load a record
```
selectRecordInDataset(ds, rec)
  → RecordLoader.load
      ├─ gateway.getDataset + gateway.listEntities      → session.entities/schema
      ├─ per view: extension.addRecordSeed(...)          → widget seeds
      ├─ loadEveryKind → SEED_LOADERS[kind].load(...)  (gateway.listAnnotations(resource, …))
      │      → each row → persistedAnnotation(row, {kind, viewId, geometry})
      │      → session.annotations: LocalAnnotation {persisted:true, review}
      │      → a kind whose list failed: nothing seeded, reported; the others read
      └─ create widgets (layoutPlanner)
  → widgets mount, build Scene2DContext, renderers.sync() draws the seeded boxes
```

### B) Draw a box and assign its entity
```
drawBBoxTool (pointer down→move→up)
  → transient rubber-band rect (tool-owned)            // preview, not in model
  → on up: collection.add({…, entityId:"", persisted:false})  // becomes a draft
  → renderer.sync() draws it dashed
  → ctx.beginPendingAnnotation({label, onConfirm, onCancel})
        → manager.pendingAnnotation set → RightPanel shows SaveAnnotationForm
  → user picks existing / new entity → confirmPendingAnnotation(choice)
        → commitDraftWithEntity(annotation, choice, ctx)   // shared, kind-agnostic
              ├─ collection.setEntity(...)  (id + snapshot)
              └─ builder.buildCreate(...)  →  mutations.queue(entityCreate?, annCreate)
```
3D is the same shape: `PointCloudWidget.handleNewBoxSave` adds the draft +
`beginPendingAnnotation`; `commitDraftWithEntity` does the rest.

### C) Edit geometry
```
tool drags an existing box → commitGeometryEdit(ctx, id, newGeometry)
                              // the box editor keeps the box inside the image first
  → collection.setGeometry(id, newGeometry)            // optimistic, shared
  → draft?      mutations.patchPendingCreate(...)       // its create carries the edit
  → persisted?  queueContentEdit                        // shared with flow F
       body = buildUpdate(annotation)                   // the status shown is left
                                                        //   alone: an edit stays in
                                                        //   review until saved (§8)
       body says what persistedContent says?           // a drag undone by hand
            → nothing queued; a content edit queued earlier for the row is
              dropped; an unsaved Accept stays queued, as the status alone
       otherwise
            → mutations.upsertUpdate(body + {review_status: "accepted"} while
                                     an unsaved Accept stands)
                                                        // one pending update per box,
                                                        // keeping an unsaved Accept
```

"Says the same" is judged the way the server judges a change: the body the
kind's `buildUpdate` makes from the edited annotation against the one it makes
from `persistedContent`, the model's score columns ignored on a model's row
(the ones its kind's seed loader declares, `review.scoreFields`, which the
interface sends as 1), and numbers equal within
a float32 round trip (`FLOAT32_ROUND_TRIP_TOLERANCE`, 2⁻²⁰ relative), the
precision the dataset stores coordinates in. Kind-agnostic: only the kind's own
`buildUpdate` is used — which is why it must build the body from the annotation
alone, a record-scoped kind keeping the row's own view and format (bbox3d).

### D) Save (persist to backend)
```
flushSave()                                    // resolves: nothing left unsaved?
  → note the open record, and whether anything is queued or on the wire
  → MutationQueue.flush()
       sort: entityCreate < annCreate < annDelete < entityDelete
       for each, sendIfStillQueued — looked at again after every await:
            dropped meanwhile, or the queue reset? → not sent
            names an entity whose create is still queued?
                 → send that create first, then look again
            out of pending, inFlight; recordWrite; gateway.create/update/delete…
       on success: writesLanded++; annotation create → persisted = true
       on failure: undo recordWrite
            refused (4xx)? → stored nothing
            otherwise      → writesLanded++: it may have been stored
            abandoned create? → not retried; its delete dropped on a 4xx,
                                kept otherwise
            any other write → back to the head of the queue
  → another save still running? → false; its result is not ours
  → another record open now? → false; nothing read back
  → something was sent? → readBack({annotations: the save did not fail})
       → note writesLanded                     // a write landing later moves it
       → reloadEntities(no write landed since) (token-guarded → session.entities)
       → annotations, and still no write landed since?
            → reloadAnnotations({stillWanted: no write landed since, holdsWork})
                 // entities first: labels read them. The server decides what a
                 // save stored — a model's row a person edited comes back
                 // "accepted" — so the rows are read back, and merged
                 // (takeRowsRead): work queued or on the wire, drafts,
                 // annotations deleted here, and every annotation of a kind
                 // whose list failed stay as they are here; a shape held
                 // by a gesture becomes its row, its node left alone by the
                 // renderer, and the gesture commits onto that row
  → failed? → false; the failed work stays as left
  → another record open now? → false
  → select(null); return nothing unsaved
```

### E) Delete (+ backend orphan cascade)
```
deleteLocalAnnotation(annotation, collection, mutations, widgetId, cancelGesture?)
     // the one choke point: the 2D select tool (Delete/Backspace), the image
     // widget's trash button, the bbox3d HUD's delete (BBox3DSession.deleteBox),
     // the review controller's Reject, manager.deleteAnnotation
  deleteGestureFor(annotation)                 // what the controls call it
     "delete"  anything not reviewable: a person's annotation, a draft
     "reject"  a model's stored annotation, whatever its status
  → cancelGesture()                            // a resize or a drag under way in
       // the widget lets go first: seam.discardStagedWork → each raised holder's
       // discard — the shape back as stored, the gesture stopped, nothing
       // committed — so what follows applies to the row as stored
  → one branch for both: a Reject is a delete
        mutations.dropForLocalAnnotation(id)    // its queued update, an entity a
                                                //   reassignment queued for it, a
                                                //   draft's creates
        persisted?  mutations.queue({op:"delete", resource, id})   // annotation only
  → collection.remove(id)                      // the selection goes with it
  → (flush) DELETE …/{resource}/{id}?prune_orphan_entity=true
        → backend deletes the entity iff no stored row names it any more:
          an annotation of any kind, a child entity, a dynamic state (§2)
```

What the queue holds for a stored row is dropped before its delete is queued,
whoever made the row, a person's included: an edit of a row about to be deleted
would only be sent to be undone, and an entity a reassignment made for it would
be left named by nothing.

A delete pressed while the mouse still holds a resize or a drag would otherwise
let the gesture go on over a shape no longer there — Konva throwing at the next
move of a resized box, a point's drag leaving its flag raised for good. So the
gesture is cancelled first, through the one path Discard takes for a widget
(`SceneContextBase.discardStagedWork` → `WorkspaceManager.discardStagedWork`):
every holder of that widget whose flag is raised runs its discard, then the
widget's flags are lowered; another widget's work stays. No kind knows a delete
can interrupt its gesture. The select tool passes it on Delete/Backspace; the
image widget's trash button passes it only while the select tool is active —
the only tool under which a resize or a drag runs — since a draw tool's staged
work is a shape not drawn yet. The HUD's delete passes none: it closes its own
confirm, and the box it held goes with it.

Both buttons that delete read `deleteGestureFor` to say what they will do. The
image widget's trash button is named by its action — "Reject selected (Del)" for
a model's annotation, "Delete selected (Del)" otherwise and while nothing is
selected —, its tooltip adding on a Reject that rejecting deletes; and with
nothing selected, why it does nothing goes in its tooltip and its accessible
description (an `sr-only` span it points to with `aria-describedby`), never its
name: "Select an annotation to delete or reject it". The bbox3d HUD's button
reads "Reject" or "Delete", through `BBox3DSession.editingDeleteGesture`, its
tooltip saying that rejecting deletes.

### F) Reassign an entity (existing box)
```
reassignEntity(annotation, choice, ctx)
  → collection.setEntity(id, newEntityId)   (+ queue entityCreate if "new")
  → queueContentEdit (flow C)                // body carries the new entity_id;
                                             // the entity it already had → nothing
  → (flush) PUT …?prune_orphan_entity=true
        → backend validates the new entity exists, then prunes the OLD one if no
          stored row names it any more (§2)
```

### G) Accept or reject a model's annotation
```
review.accept(id)                                   // ReviewController
  → commitAccept(annotation, {collection, mutations, widgetId})
       canAccept is false → nothing            // not reviewable, or not shown
                                                //   pending (mayAccept)
       → mutations.upsertUpdate({op:"update", resource, id,
                                 body: {…the queued content edit's body, if any,
                                        review_status: "accepted"}})
       → collection.setReview(id, {…review, status: "accepted"})
  → the chips may now hide it (the Accepted chip off) → selection dropped
  → (flush) PUT …/{resource}/{id}  {review_status: "accepted", …an edit}

review.reject(id)
  → deleteLocalAnnotation(…)  when its gesture is "reject" (flow E)
       // true when the delete was queued: the row leaves the list and every
       // canvas; false when refused (no such row, a person's, a draft)
```

Accept is offered over an unsaved edit and carries it: the row's one queued
update holds the edit and `accepted`, and the server stores both. An edit after
an Accept keeps it (flow C). Discard undoes all of it: it empties the queue,
puts the stored content and status back at once, and reads the record again. A
Reject is a delete: it throws the row's unsaved work away, and only Discard —
with the rest of the record's unsaved work — brings the row back before Save;
nothing does after.

---

## 8. Reviewing a model's annotations

A model's annotation arrives `pending`, and `accepted` is where a person's review
leaves it; a person's annotation carries no status (`ReviewStatus`,
`src/pixano/schemas/annotations/entity_annotation.py`;
`docs/specs/backend-processing.md` §19). The server owns that vocabulary; the
interface reads it on every annotation it loads, and shows it on the canvas.
Nothing in it is kind-specific: a kind's annotations carry their review state as
soon as its seed loader builds through the shared envelope, and no kind name
appears in the modules below.

**What is reviewable.** `isReviewable(a)`: persisted, `review.sourceType ===
"model"`, and a known status. A model's row stored with no status — re-imported
from JSONL, or a legacy smart-tracking mask — reads as `pending`, as the server
reads it (`review_status_of`, `src/pixano/schemas/annotations/review.py`). A
person's annotation and a draft are not reviewable.

**The pieces, split to keep the import graph acyclic.**

- `annotations/reviewStatus.ts` — the status vocabulary (`REVIEW_STATUS`, and
  the chip keys `REVIEW_FILTER_KEYS`: the statuses plus `"human"`),
  `AnnotationReview`, `reviewOf(row, scoreFields)` (lenient: never throws; the
  score is read from the columns the kind declares — the first holding a number,
  or a list's first valid number — and the declaration is kept on
  `AnnotationReview.scoreFields`), `isReviewable`, `reviewFilterKeyOf`,
  `isShownByReviewFilter`, `storedStatusOf`, `isAcceptUnsaved` (shown accepted,
  not stored so), `mayAccept` (a row shown pending), `storedStatusAfterWrite`
  (what a write stores), `carriesContent` (whether an update body changes
  content rather than carrying an Accept alone). Type-only imports, so seed loaders and the label renderer
  can use it without the registry cycle `viewScopedSeedLoader.ts` describes. No
  display text, and no column of any
  kind: each kind's seed loader declares its score columns (`scoreFields`:
  `["confidence"]` for bbox and bbox3d, `["confidences"]` for classification,
  none for the others), as its backend schema does in `MODEL_SCORE_FIELDS`.
- `annotations/persistedAnnotation.ts` —
  `persistedAnnotation(row, {kind, viewId, geometry, scoreFields}, ctx)`, the
  one `LocalAnnotation` envelope, `review` and `persistedContent` included. Both
  `createViewScopedSeedLoader` and the record-scoped `bbox3dSeedLoader` use it,
  so no loader can forget the review.
- `annotations/payloadBuilders.ts` — `canAccept` (the one test every control
  offering Accept reads), `commitAccept` (flow G), `deleteGestureFor` and
  `deleteLocalAnnotation` (flow E: every delete, a Reject included), next to the
  other commit helpers.
- `workspace/reviewController.svelte.ts` — `ReviewController`, the review of the
  open record for a panel to show, `manager.review`: the rows (the annotations
  the chips let through, of the entities the Entities tab shows — each with its
  kind, label, model, version, score, status, `canAccept`, `canReject` and
  whether it is selected), the per-chip counts, the chips (`isHidden`, `toggle`,
  `isShown`), the record-wide unsaved count (`unsavedCount`, read from the
  navigator — the manager's own count), select, accept and reject, save and
  whether there is anything to save (`canSave`: a queued change), discard and
  whether there is anything to discard (`canDiscard`). Narrow injected deps —
  `{session, sink: MutationSink, navigator: {save, unsavedCount, hasUnsavedWork, discardChanges}}`
  — never the `WorkspaceManager`. It holds no review state of its own: statuses
  live on the annotations, decisions on the queue, chips on the session. No
  panel renders it yet.

**Reject deletes.** A model's annotation is rejected by deleting it, like any
row: `deleteLocalAnnotation` is the single choke point every delete gesture goes
through (flow E) — the Delete key, the image widget's trash button, the 3D HUD,
the review controller's Reject —,
and the server prunes its entity when nothing else names it. The controls say
so: on a model's annotation, whatever its status, they read "Reject", and their
tooltip says that rejecting deletes (`deleteGestureFor`). No row is left to mark
the rejection, so a later run of the model may propose it again — a consequence
accepted with the rule. A Reject, like any delete, throws the row's unsaved work
away — an edit, an entity a reassignment queued for it. A Reject takes the row off every canvas at once; before
Save, only Discard brings it back, with the rest of the record's unsaved work,
and nothing does after Save: there is no undo of one Reject.

**Decisions are mutations.** An Accept is an update queued on the
`MutationQueue` and sent by Save, like any edit — one write path: the status
alone, or riding on the row's unsaved edit. The queue holds one pending update
per row, so an Accept and an edit of one row ride in one update, whichever came
first (flows C and G), and the update belongs to the gesture that last wrote its
body: `upsertUpdate` takes the newer `widgetId` with it. A Reject is the row's
delete (flow E), which drops the row's unsaved work. Decisions taken through the
controller carry `REVIEW_PANEL_SOURCE_ID`. No counter reads that stamp: every
widget toolbar and the controller give one number, the record's unsaved items
(`manager.unsavedCount`, which the controller reads through its navigator), so a
decision taken through it reads as unsaved on every canvas too. Discard throws
the record's unsaved work away from wherever it is pressed
(`manager.discardChanges`: it drops the work tools hold, puts each annotation
back as stored, and reads the entities and the rows again).

**Shown status and stored status.** `AnnotationReview.status` is what the screen
shows; `storedStatus` is what the dataset holds, read with the row and moved
only by a write of it (`recordWrite`, §5). There is no transition table to
mirror: the one decision is `accepted`, from `pending`, and no update takes a
row back. The stored status tells an unsaved Accept (shown accepted, stored
pending — `isAcceptUnsaved`), which an edit carries on, and is what Discard
puts back. A row's `canAccept`
comes from `canAccept` — a model's stored row shown pending — and its
`canReject` from `deleteGestureFor` — a model's stored row, whatever its status.

**An edit stays in review until it is saved.** A content edit of a model's row —
a drag, a resize, a reassignment, a box moved under the 3D HUD — leaves the row
shown `pending`, and Accept offered: unsaved, it is the reviewer's work in
progress. The workspace's Save — the toolbar's, or the controller's — sends it,
the server stores the row `accepted`, keeping the model's provenance and score,
and the row reads accepted as the write leaves (`recordWrite`, §5). Accept over
the edit sends both in one update. An edit that puts the content back as stored
is no edit: nothing is queued but an unsaved Accept (flow C). The 3D HUD's "Save"
button stages, it does not save: it confirms the move into the record's unsaved
work (`BBox3DSession.save` → `commitGeometryEdit`), so the box still reads
pending after it, until the workspace's Save. The 3D HUD stages nothing for a
box it opened and nobody moved (`BBox3DSession.save`), comparing the staged box
with the editor's own round trip of the stored one, each number within a
float32 round trip — flow C's rule (`sameValue`); a moved box keeps its stored
rotation unless it was turned, and `bbox3dPayloadBuilder` writes the box's own
view and format, so a HUD Save that changed nothing does not accept the box.

**The status chips are display-only.** `session.hiddenReviewStatuses` (default
empty: nothing hidden) holds the chips switched off — `pending`,
`accepted`, or `"human"` for every annotation no model produced. It is read by
`manager.isShownByReview` (`review.isShown`), which `buildSeam` hands every
widget's `ViewScopedAnnotations` as its display predicate (§5), so it applies to
every kind and no renderer or tool knows it exists. Drafts always show, and
`find` and save are never filtered. The controller's `toggle` sets it, one chip
at a time, and drops a selection the chips now hide — as an Accept does when the
Accepted chip is off.

**On the canvas.** The shared `EntityLabels2D` writes "entity · status" on a
model's annotation, on a colour per status — pending or accepted
(`REVIEW_TAG_COLOR_*` in `scene2dStyleConstants.ts`) —, even when the entity has
no text to show, and rebuilds a label when its text or its colour changes —
which also recolours a draft's label once it is saved. A person's annotation and
a draft keep their saved and unsaved colours. Kinds drawn with those labels show
the status on the canvas (bbox, mask, keypoints, multi-path); classification and
bbox3d — in 3D and projected — show no status.

---

## 9. Reactivity & rendering notes

- Stateful domain classes live in `.svelte.ts` files so the runes compiler picks
  up `$state`/`$derived`/`$effect` (`AnnotationCollection`, `MutationQueue`,
  `WorkspaceSession`, `ReviewController`, `BoxEditor`, `PointCloudCamera`).
- **2D**: `ImageWidget` re-runs `syncRenderers()` in an `$effect` that reads
  `annotations.items.length`, `annotations.selectedId`, and
  `manager.visibleEntityIds`; the renderer reconciles Konva nodes. Computing
  `items` runs the review display filter, which reads the chips and each
  annotation's `review`, so a chip toggle or an Accept re-runs the reconcile too
  (an Accept replaces `review` in place through `setReview`).
- **3D**: `PointCloudScene` uses **Threlte on-demand rendering** — it redraws on
  reactive invalidation. Nothing is pushed into the scene: it mounts one component
  per `RENDERER_FACTORIES_3D` entry and each pulls its kind from
  `ctx.collection.byKind(...)` (`BBox3DRenderer.svelte`). The `BoxEditor`
  (`kinds/3d/bbox3d/boxEditor.svelte.ts`) owns pointer interaction and a reactive
  preview. (Implication: a thrown error in a save-time recompute can stall the
  on-demand loop — see the freeze investigation.)

---

## 10. Where everything lives (file map)

```
ui/apps/web/src/lib/
├─ api/annotations.ts                      REST fetch wrappers
├─ workspace/
│  ├─ workspaceManager.svelte.ts           orchestrator (composition root)
│  ├─ workspaceSession.svelte.ts           record-scoped shared state
│  ├─ recordLoader.ts                       (dataset,record) → widgets + data
│  ├─ mutationQueue.svelte.ts               pending writes + flush
│  ├─ reviewController.svelte.ts            the review of the record: rows, chips,
│  │                                         counts, Accept/Reject, Save/Discard
│  ├─ datasetGateway.ts                     I/O seam (interface + http impl)
│  ├─ unsavedWork.ts                        the one rule of the record's unsaved count
│  ├─ datasetLayout.ts                      per-dataset layout rules (snapshot/
│  │                                         resolve/parse) — no storage access
│  └─ datasetLayoutRepository.ts            layout storage seam (+ localStorage impl)
├─ annotations/
│  ├─ annotationCollection.svelte.ts        LocalAnnotation, AnnotationStore,
│  │                                         AnnotationCollection, ViewScopedAnnotations
│  ├─ buildPayloads.ts                       local→REST bodies + entity-create + sort
│  ├─ payloadBuilders.ts                     PAYLOAD_BUILDERS + accept/delete/commit/reassign helpers
│  ├─ seedLoaders.ts                         SEED_LOADERS (REST→local)
│  ├─ persistedAnnotation.ts                 the LocalAnnotation envelope of a stored row
│  ├─ reviewStatus.ts                        review vocabulary + pure rules (type-only imports)
│  ├─ scene/
│  │  ├─ registry2d.ts / registry3d.ts       TOOLS_*, RENDERER_FACTORIES_*
│  │  ├─ sceneContext.ts                      SceneContextBase, SeamContext (+ staged
│  │  │                                       work), Scene2DReadContext, Scene2DContext,
│  │  │                                       Scene3DContext, MutationSink
│  │  ├─ toolDefinition.ts                    ToolDefinition (shared 2D/3D metadata)
│  │  ├─ renderer.ts / tool.ts                Renderer/Editor + Tool contracts;
│  │  │                                       isFormFieldTarget (window key guard)
│  │  ├─ selectTool2D.ts                      kind-agnostic select/delete tool
│  │  ├─ flatCoordsEditor2D.ts                shared vertex editor (keypoints, multi-path)
│  │  ├─ entityLabels2D.ts                    shared label rendering
│  │  ├─ scene2dGeometry.ts                   pixel↔normalized helpers, PixelFrame
│  │  └─ scene2dStyleConstants.ts             shared 2D draw styling
│  └─ kinds/<2d|3d>/<kind>/                  per-kind: payloadBuilder, seedLoader,
│                                            renderer, editor/tool (+ 3D: overlay/session/hud)
└─ components/
   ├─ widgets/AnnotationToolbar.svelte        shared toolbar; sceneSeam.ts (buildSeam)
   ├─ widgets/image/ImageWidget.svelte        Konva host, builds Scene2DContext
   ├─ widgets/point-cloud/PointCloudWidget…   Threlte host; PointCloudScene, camera
   └─ widgets/TextWidget.svelte               Tiptap host — display only, no seam yet
```

---

## 11. Contracts cheat-sheet

| Contract | Defined in | Implemented / consumed by |
|---|---|---|
| `DatasetGateway` | `workspace/datasetGateway.ts` | `httpDatasetGateway`; consumed by loader + queue; a refused write rejects with an `ApiError` carrying its 4xx status |
| `DatasetLayoutRepository` | `workspace/datasetLayoutRepository.ts` | `localStorageDatasetLayoutRepository`; consumed by loader + manager |
| `AnnotationStore` | `annotations/annotationCollection.svelte.ts` | `AnnotationCollection`, `ViewScopedAnnotations` |
| `MutationSink` | `scene/sceneContext.ts` | `MutationQueue`; consumed by tools/widgets and the `ReviewController` |
| `ReviewControllerDeps` / `ReviewNavigator` | `workspace/reviewController.svelte.ts` | built by `WorkspaceManager` (`navigator` = `flushSave` as `save` + `unsavedCount` + `hasUnsavedWork` + `discardChanges`) |
| `Scene2DContext` | `scene/sceneContext.ts` | built by `ImageWidget`; consumed by tools/editors (renderers get the read-only `Scene2DReadContext`) |
| `StagedWorkFlag` (`SceneContextBase.claimStagedWork` / `releaseStagedWork` / `discardStagedWork`) | `scene/sceneContext.ts` | built by `buildSeam` (→ `manager.claimStagedWork` / `releaseStagedWork` / `discardStagedWork`, stamped with the widget id); claimed by each holder of unconfirmed work — a 2D tool's handler, the bbox, mask, multi-path and keypoints editors (a drag; the bbox editor's resize too) — with the callback Discard calls, and a delete pressed mid-gesture calls first for its widget; each raised flag counts once in `WorkspaceManager.unsavedCount` |
| `PayloadBuilder` | `payloadBuilders.ts` | per-kind builders in `kinds/.../` |
| `AnnotationSeedLoader` | `seedLoaders.ts` | per-kind seed loaders, each building its annotations through `persistedAnnotation` |
| `ResourceMutation` | `annotations/types.ts` | the unit the queue flushes |
| `LocalAnnotationLocator` | queue ctor | `findLocalAnnotation: (id) => session.annotations.find(id)` (persisted flip) + `recordQueued` (the content a body carries, kept as it is queued) + `recordWrite` (what a write stores, undone on failure) |

These interfaces are the joints: depend on them, not on `WorkspaceManager`, and a
new kind / a fake gateway / a new scene type slots in without touching the rest.
