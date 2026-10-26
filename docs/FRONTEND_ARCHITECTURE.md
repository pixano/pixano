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
    stored row names it
    (`_entity_is_named`): an annotation of any table, a child entity, an entity
    dynamic state. One mechanism, every kind, server-side (the only place that
    sees every reference — the frontend loads one record at a time). The write,
    the check and the entity's delete hold the request's one write lock, so no
    write naming the entity lands between the check and the delete: one arriving
    meanwhile is refused as a busy dataset's 409. An entity that only a child
    entity, a dynamic state, a message's `entity_ids` or a relation's end still
    names stays once its last annotation is deleted or moved.

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
| `deleteAnnotation` | `api/annotations.ts` | `DELETE …/{resource}/{id}?prune_orphan_entity=true` | a 404 counts as done, any other failure throws an `ApiError` with its status |

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
 └─ pendingAnnotation                     // box awaiting its entity choice
```

Representative API: `openRecord` (the way to switch records, or to open the
same one again: clears the workspace, unsaved changes included, then
`selectRecordInDataset`), `flushSave`, `discardChanges`, `queueMutation`,
`upsertUpdateMutation`, `deleteAnnotation`, `beginPendingAnnotation` /
`confirmPendingAnnotation` / `cancelPendingAnnotation`, `isEntityVisible` /
`toggleEntityVisible` / `showAllEntities`, `claimStagedWork` /
`releaseStagedWork` (a flag per holder of work a tool keeps unconfirmed, reached
through the seam — "Unsaved work and saves" below), `unsavedCount` (how many
items of the record are unsaved, the one count every unsaved counter shows —
"Unsaved work and saves" below), `hasUnsavedWork` (that count is not 0),
`saveDatasetLayout` / `restoreOpeningLayout` / `fitLayoutToViewport`. Getters
forward to the session/queue (`annotations`, `entities`, `pendingCount` — the
request on the wire included — `pendingMutations` — the queued ones only —
`saving`, …).

`flushSave()` resolves to a boolean: true when the save went through **and**
nothing is left unsaved — `unsavedCount` is 0: no queued change, no request on
the wire, no draft, no entity form open, no work a tool holds staged. It is
false when the save failed (the error is on `saveError`), or when work is still
unsaved — begun during the save, or held in a tool.

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
stagedWork : ReadonlyMap<string, StagedWorkHolder>  // raised staged-work flags
```
Held on a tiny shared object so each sub-service depends on this narrow type, not
on the whole manager.

`stagedWork` shows the raised flags of work no mutation carries yet — a
polygon's points before Enter, a box being resized, a shape being dragged —
each with its widget and the callback that drops the work. Each holder raises
and lowers its own flag through its widget's seam (`claimStagedWork`, "Unsaved
work and saves" below); while any is raised the record is not all saved, and
each raised flag counts as one unsaved item (`unsavedCount`). The manager alone
writes the flags, in a private map it publishes here as a copy — always
replaced, never mutated — and `clearWorkspace` / `reset()` empty it with the
widgets.

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

`reloadEntities()` refetches just the entity list after a save (token-guarded) so
the panel/picker reflect created/pruned entities.

### `MutationQueue` (`workspace/mutationQueue.svelte.ts`)
Owns the list of pending writes and the flush lifecycle. Implements **`MutationSink`**:
`queue`, `upsertUpdate` (replace the last queued update for the same
resource+id, taking the newer gesture's `widgetId` with its body),
`patchPendingCreate` (merge into a not-yet-sent create), `dropForLocalAnnotation`.
Plus reactive `pending`, `inFlight`, `count`, `saving`, `saveError`.

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
   and none dropped while the flush ran is sent.
3. On a successful **create** of an annotation, flip its local `persisted = true`
   via the **`LocalAnnotationLocator`** (`findLocalAnnotation(id)` → the session's
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
first, whenever it was queued.

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
the shape back nor drops its move: the node stays where the gesture has it, and
the gesture is committed by id when the pointer is let go — only one the editor
saw begin.

A widget lowers its holders' flags as it closes (`releaseStagedWork`), since
nothing in it can confirm that work any more. While a flag is raised, a save
reports work left: `flushSave` resolves false. Each raised flag counts as one
item of `unsavedCount`, so the counters never read 0 while a tool holds work.
Discard calls every raised flag's discard — a tool forgets its points, a resize
or a drag stops and commits nothing — and is offered whenever anything is
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
{ id, entityId, kind, viewId, geometry: G, persisted, entity? }
```
- `kind ∈ AnnotationKind` (`"bbox" | "bbox3d" | "mask" | "keypoints" |
  "multi_path" | "classification"`).
- `geometry` is typed per kind via `GeometryByKind` (`bbox` → `[x,y,w,h]` norm;
  `bbox3d` → `{coords, format, rotation}` in Lance space; each other kind's shape
  is declared in its own `kinds/<2d|3d>/<kind>/<kind>Types.ts`).
- `persisted=false` ⇒ a **draft** (drawn but not yet POSTed). `entity` is a snapshot
  of the parent entity's fields so labels render without a refetch.

### `AnnotationCollection` — the record-scoped source of truth
`$state` list + `selectedId`, with `find/byKind/add/remove/select/setGeometry/
setEntity`. **Owned by `WorkspaceSession`, one instance per record load, shared by
every widget.** Optimistic edits mutate `geometry` in place; the `MutationQueue` is
the ledger of what still has to reach the backend.

### `ViewScopedAnnotations` — the per-widget facade
Implements the same **`AnnotationStore`** interface but scopes reads to *one view*:
`_visible(a) = a.viewId === thisView || RECORD_SCOPED_KINDS.has(a.kind)`.
- `RECORD_SCOPED_KINDS = {bbox3d}` ⇒ a 3D box passes every view filter, which is
  what lets an image widget **project** it.
- Reads (`items`, `byKind`, `find`, **and** `selected`/`selectedId`) are view-scoped;
  **writes pass straight through** to the shared collection, so every other widget
  sees them immediately.

```
WorkspaceSession.annotations  (record: all kinds, all views)
        ▲ writes                         ▲ reads (scoped)
        │                                │
  ImageWidget A ── ViewScopedAnnotations(view A) ─┐
  ImageWidget B ── ViewScopedAnnotations(view B) ─┤ same underlying collection
  PointCloudWidget ── reads byKind("bbox3d") ─────┘ (3D reads the raw collection)
```

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
      │      → map rows → session.annotations.add(LocalAnnotation, persisted:true)
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
  → mutations.upsertUpdate(buildUpdate(...))            // one pending update per box
```

### D) Save (persist to backend)
```
flushSave()
  → MutationQueue.flush()
       sort: entityCreate < annCreate < annDelete < entityDelete
       for each, sendIfStillQueued — looked at again after every await:
            dropped meanwhile, or the queue reset? → not sent
            names an entity whose create is still queued?
                 → send that create first, then look again
            out of pending, inFlight; gateway.create/update/delete…
       on success: annotation create → persisted = true
       on failure:
            abandoned create? → not retried; its delete dropped on a 4xx,
                                kept otherwise
            any other write → back to the head of the queue
  → reloadEntities()  (token-guarded refetch → session.entities fresh)
```

### E) Delete (+ backend orphan cascade)
```
deleteAnnotation(annotation)            // 2D: via ctx + deleteLocalAnnotation; 3D: manager
  → persisted?  mutations.queue({op:"delete", resource, id})   // annotation only
     draft?     mutations.dropForLocalAnnotation(id)            // unsend its creates
  → collection.remove(id)
  → (flush) DELETE …/{resource}/{id}?prune_orphan_entity=true
        → backend deletes the entity iff no stored row names it any more:
          an annotation of any kind, a child entity, a dynamic state (§2)
```

### F) Reassign an entity (existing box)
```
reassignEntity(annotation, choice, ctx)
  → collection.setEntity(id, newEntityId)   (+ queue entityCreate if "new")
  → mutations.upsertUpdate(buildUpdate(...))  // body carries the new entity_id
  → (flush) PUT …?prune_orphan_entity=true
        → backend validates the new entity exists, then prunes the OLD one if no
          stored row names it any more (§2)
```

---

## 8. Reactivity & rendering notes

- Stateful domain classes live in `.svelte.ts` files so the runes compiler picks
  up `$state`/`$derived`/`$effect` (`AnnotationCollection`, `MutationQueue`,
  `WorkspaceSession`, `BoxEditor`, `PointCloudCamera`).
- **2D**: `ImageWidget` re-runs `syncRenderers()` in an `$effect` that reads
  `annotations.items.length`, `annotations.selectedId`, and
  `manager.visibleEntityIds`; the renderer reconciles Konva nodes.
- **3D**: `PointCloudScene` uses **Threlte on-demand rendering** — it redraws on
  reactive invalidation. Nothing is pushed into the scene: it mounts one component
  per `RENDERER_FACTORIES_3D` entry and each pulls its kind from
  `ctx.collection.byKind(...)` (`BBox3DRenderer.svelte`). The `BoxEditor`
  (`kinds/3d/bbox3d/boxEditor.svelte.ts`) owns pointer interaction and a reactive
  preview. (Implication: a thrown error in a save-time recompute can stall the
  on-demand loop — see the freeze investigation.)

---

## 9. Where everything lives (file map)

```
ui/apps/web/src/lib/
├─ api/annotations.ts                      REST fetch wrappers
├─ workspace/
│  ├─ workspaceManager.svelte.ts           orchestrator (composition root)
│  ├─ workspaceSession.svelte.ts           record-scoped shared state
│  ├─ recordLoader.ts                       (dataset,record) → widgets + data
│  ├─ mutationQueue.svelte.ts               pending writes + flush
│  ├─ datasetGateway.ts                     I/O seam (interface + http impl)
│  ├─ unsavedWork.ts                        the one rule of the record's unsaved count
│  ├─ datasetLayout.ts                      per-dataset layout rules (snapshot/
│  │                                         resolve/parse) — no storage access
│  └─ datasetLayoutRepository.ts            layout storage seam (+ localStorage impl)
├─ annotations/
│  ├─ annotationCollection.svelte.ts        LocalAnnotation, AnnotationStore,
│  │                                         AnnotationCollection, ViewScopedAnnotations
│  ├─ buildPayloads.ts                       local→REST bodies + entity-create + sort
│  ├─ payloadBuilders.ts                     PAYLOAD_BUILDERS + delete/commit/reassign helpers
│  ├─ seedLoaders.ts                         SEED_LOADERS (REST→local)
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

## 10. Contracts cheat-sheet

| Contract | Defined in | Implemented / consumed by |
|---|---|---|
| `DatasetGateway` | `workspace/datasetGateway.ts` | `httpDatasetGateway`; consumed by loader + queue; a refused write rejects with an `ApiError` carrying its 4xx status |
| `DatasetLayoutRepository` | `workspace/datasetLayoutRepository.ts` | `localStorageDatasetLayoutRepository`; consumed by loader + manager |
| `AnnotationStore` | `annotations/annotationCollection.svelte.ts` | `AnnotationCollection`, `ViewScopedAnnotations` |
| `MutationSink` | `scene/sceneContext.ts` | `MutationQueue`; consumed by tools/widgets |
| `Scene2DContext` | `scene/sceneContext.ts` | built by `ImageWidget`; consumed by tools/editors (renderers get the read-only `Scene2DReadContext`) |
| `StagedWorkFlag` (`SceneContextBase.claimStagedWork` / `releaseStagedWork`) | `scene/sceneContext.ts` | built by `buildSeam` (→ `manager.claimStagedWork` / `releaseStagedWork`, stamped with the widget id); claimed by each holder of unconfirmed work — a 2D tool's handler, the bbox, mask, multi-path and keypoints editors (a drag; the bbox editor's resize too) — with the callback Discard calls; each raised flag counts once in `WorkspaceManager.unsavedCount` |
| `PayloadBuilder` | `payloadBuilders.ts` | per-kind builders in `kinds/.../` |
| `AnnotationSeedLoader` | `seedLoaders.ts` | per-kind seed loaders |
| `ResourceMutation` | `annotations/types.ts` | the unit the queue flushes |
| `LocalAnnotationLocator` | queue ctor | `(id) => session.annotations.find(id)` (persisted flip) |

These interfaces are the joints: depend on them, not on `WorkspaceManager`, and a
new kind / a fake gateway / a new scene type slots in without touching the rest.
