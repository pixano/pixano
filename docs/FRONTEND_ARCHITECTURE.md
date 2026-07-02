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
> - [`ARCHITECTURE.md`](./ARCHITECTURE.md) — the *why* (refactor decisions D1–D6,
>   the plugin model, known debts).
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
  `ANNOTATION`, `ENTITY_DYNAMIC_STATE`, `EMBEDDING`. `dataset.info.groups.get(group)`
  returns every table in a group — this is how the backend sweeps "all annotation
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
  - **orphan-entity cascade** (opt-in `?prune_orphan_entity=true`): on delete or on
    an `entity_id`-changing update, `_entity_has_annotations(id)` scans every
    `ANNOTATION` table; if none remain, `_delete_orphan_entity(id)` removes the
    entity from its `ENTITY` table. One mechanism, every kind, server-side (the
    only place that sees every reference — the frontend loads one record at a time).

### REST surface the frontend uses (`ui/.../lib/api/annotations.ts`)
| Function | HTTP | Notes |
|---|---|---|
| `getDataset` | `GET /datasets/{id}` | schema + views |
| `listEntities` | `GET …/entities?record_id=` | record-scoped entity rows |
| `listBBoxes` / `listBBox3Ds` | `GET …/bboxes?record_id=` | annotation rows |
| `loadImageByLogicalName` / `loadPointCloudByLogicalName` | `GET …/{view}` | media + calibration |
| `createEntity` / `deleteEntity` | `POST/DELETE …/entities` | |
| `createAnnotation` | `POST …/{resource}` | kind-generic (resource = table) |
| `updateAnnotation` | `PUT …/{resource}/{id}?prune_orphan_entity=true` | geometry / entity reassign |
| `deleteAnnotation` | `DELETE …/{resource}/{id}?prune_orphan_entity=true` | |

---

## 3. The DatasetGateway — the I/O seam

`workspace/datasetGateway.ts` defines **`RecordReadGateway`** (reads) and the full
**`DatasetGateway`** (reads + `createEntity`, `deleteEntity`, `createAnnotation`,
`updateAnnotation`, `deleteAnnotation`). The default `httpDatasetGateway` forwards
to `api/annotations.ts`.

Why it exists: the `MutationQueue` and `RecordLoader` depend on this **interface**,
not on `fetch`. Tests pass an in-memory fake; nothing else changes. The frontend
never calls `fetch` outside `api/`.

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

Representative API: `selectRecordInDataset`, `flushSave`, `queueMutation`,
`upsertUpdateMutation`, `deleteAnnotation`, `beginPendingAnnotation` /
`confirmPendingAnnotation` / `cancelPendingAnnotation`, `isEntityVisible` /
`toggleEntityVisible` / `showAllEntities`. Getters forward to the session/queue
(`annotations`, `entities`, `pendingCount`, `saving`, …).

### `WorkspaceSession` (`workspace/workspaceSession.svelte.ts`)
The record-scoped truth, replaced on every load:
```
datasetId · recordId · entities[] · entitySchemaName · entitySchemaFields
annotations : AnnotationCollection      // the shared model (§5)
visibleEntityIds : Set<string> | null   // entity-driven visibility (null = all)
```
Held on a tiny shared object so each sub-service depends on this narrow type, not
on the whole manager.

### `RecordLoader` (`workspace/recordLoader.ts`)
`load(datasetId, recordId, viewport)`:
1. Set `session.datasetId/recordId`; reset `entities`, `annotations`,
   `visibleEntityIds`. A `loadToken` guards every async write so a fast
   record-switch can't let a stale fetch overwrite the new record.
2. In parallel: `getDataset` + `listEntities`.
3. For each declared view, ask each registered **extension** `addRecordSeed(...)`;
   run the per-kind **`SEED_LOADERS`** to fetch that record's annotation rows and
   map them into the shared `AnnotationCollection`.
4. Create one widget per claimed view (layout via `layoutPlanner`).

`reloadEntities()` refetches just the entity list after a save (token-guarded) so
the panel/picker reflect created/pruned entities.

### `MutationQueue` (`workspace/mutationQueue.svelte.ts`)
Owns the list of pending writes and the flush lifecycle. Implements **`MutationSink`**:
`queue`, `upsertUpdate` (replace a pending update for the same resource+id),
`patchPendingCreate` (merge into a not-yet-sent create), `dropForLocalAnnotation`.
Plus reactive `pending`, `count`, `saving`, `saveError`.

`flush()`:
1. `sortMutations(pending)` by **`mutationPriority`**: `entityCreate(0) <
   annotationCreate(1) < annotationDelete(2) < entityDelete(3)` — entities are
   created before the annotations that reference them, and deleted after them.
2. POST/PUT/DELETE each via the gateway; drop it from `pending` on success.
3. On a successful **create** of an annotation, flip its local `persisted = true`
   via the **`LocalAnnotationLocator`** (`findLocalAnnotation(id)` → the session's
   collection). Drafts thus become "saved" without a per-widget lookup.

---

## 5. The shared annotation model

### `LocalAnnotation<G>` (`annotations/annotationCollection.svelte.ts`)
The one in-memory shape for **every** kind — pure data, no methods:
```ts
{ id, entityId, kind, viewId, geometry: G, persisted, entity? }
```
- `kind ∈ AnnotationKind` (`"bbox" | "bbox3d" | "mask"`).
- `geometry` is typed per kind via `GeometryByKind` (`bbox` → `[x,y,w,h]` norm;
  `bbox3d` → `{coords, format, rotation}` in Lance space).
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

## 8. End-to-end flows

### A) Load a record
```
selectRecordInDataset(ds, rec)
  → RecordLoader.load
      ├─ gateway.getDataset + gateway.listEntities      → session.entities/schema
      ├─ per view: extension.addRecordSeed(...)          → widget seeds
      ├─ SEED_LOADERS[kind].load(...)  (gateway.listBBoxes/listBBox3Ds)
      │      → map rows → session.annotations.add(LocalAnnotation, persisted:true)
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
tool drags an existing box
  → collection.setGeometry(id, newGeometry)            // optimistic, shared
  → mutations.upsertUpdate(buildUpdate(...))            // one pending update per box
```

### D) Save (persist to backend)
```
flushSave()
  → MutationQueue.flush()
       sort: entityCreate < annCreate < annDelete < entityDelete
       for each: gateway.create/update/delete…
       on annotation create success: locator → annotation.persisted = true
  → reloadEntities()  (token-guarded refetch → session.entities fresh)
```

### E) Delete (+ backend orphan cascade)
```
deleteAnnotation(annotation)            // 2D: via ctx + deleteLocalAnnotation; 3D: manager
  → persisted?  mutations.queue({op:"delete", resource, id})   // annotation only
     draft?     mutations.dropForLocalAnnotation(id)            // unsend its creates
  → collection.remove(id)
  → (flush) DELETE …/{resource}/{id}?prune_orphan_entity=true
        → backend deletes the entity iff it had no other annotation (any kind)
```

### F) Reassign an entity (existing box)
```
reassignEntity(annotation, choice, ctx)
  → collection.setEntity(id, newEntityId)   (+ queue entityCreate if "new")
  → mutations.upsertUpdate(buildUpdate(...))  // body carries the new entity_id
  → (flush) PUT …?prune_orphan_entity=true
        → backend validates the new entity exists, then prunes the OLD one if orphaned
```

---

## 9. Reactivity & rendering notes

- Stateful domain classes live in `.svelte.ts` files so the runes compiler picks
  up `$state`/`$derived`/`$effect` (`AnnotationCollection`, `MutationQueue`,
  `WorkspaceSession`, `BoxEditor`, `PointCloudCamera`).
- **2D**: `ImageWidget` re-runs `syncRenderers()` in an `$effect` that reads
  `annotations.items.length`, `annotations.selectedId`, and
  `manager.visibleEntityIds`; the renderer reconciles Konva nodes.
- **3D**: `PointCloudScene` uses **Threlte on-demand rendering** — it redraws on
  reactive invalidation. `allBboxes3d` (`$derived`) feeds the scene; the `BoxEditor`
  owns pointer interaction and a reactive preview. (Implication: a thrown error in
  a save-time recompute can stall the on-demand loop — see the freeze investigation.)

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
│  └─ datasetGateway.ts                     I/O seam (interface + http impl)
├─ annotations/
│  ├─ annotationCollection.svelte.ts        LocalAnnotation, AnnotationStore,
│  │                                         AnnotationCollection, ViewScopedAnnotations
│  ├─ buildPayloads.ts                       local→REST bodies + entity-create + sort
│  ├─ payloadBuilders.ts                     PAYLOAD_BUILDERS + delete/commit/reassign helpers
│  ├─ seedLoaders.ts                         SEED_LOADERS (REST→local)
│  ├─ scene/
│  │  ├─ registry2d.ts / registry3d.ts       TOOLS_*, RENDERER_FACTORIES_*
│  │  ├─ sceneContext.ts                      SceneContextBase, Scene2DReadContext,
│  │  │                                       Scene2DContext, Scene3DContext, MutationSink
│  │  ├─ renderer.ts / tool.ts                Renderer/Editor + Tool contracts
│  │  └─ scene2dGeometry.ts                   pixel↔normalized helpers, PixelFrame
│  └─ kinds/<2d|3d>/<kind>/                  per-kind: payloadBuilder, seedLoader,
│                                            renderer, editor/tool (+ 3D: overlay/session/hud)
└─ components/
   ├─ widgets/AnnotationToolbar.svelte        shared toolbar; sceneSeam.ts (buildSeam)
   ├─ widgets/image/ImageWidget.svelte        Konva host, builds Scene2DContext
   └─ widgets/point-cloud/PointCloudWidget…   Threlte host; PointCloudScene, boxEditor
```

---

## 11. Contracts cheat-sheet

| Contract | Defined in | Implemented / consumed by |
|---|---|---|
| `DatasetGateway` | `workspace/datasetGateway.ts` | `httpDatasetGateway`; consumed by loader + queue |
| `AnnotationStore` | `annotations/annotationCollection.svelte.ts` | `AnnotationCollection`, `ViewScopedAnnotations` |
| `MutationSink` | `scene/sceneContext.ts` | `MutationQueue`; consumed by tools/widgets |
| `Scene2DContext` | `scene/sceneContext.ts` | built by `ImageWidget`; consumed by tools/editors (renderers get the read-only `Scene2DReadContext`) |
| `PayloadBuilder` | `payloadBuilders.ts` | per-kind builders in `kinds/.../` |
| `AnnotationSeedLoader` | `seedLoaders.ts` | per-kind seed loaders |
| `ResourceMutation` | `annotations/types.ts` | the unit the queue flushes |
| `LocalAnnotationLocator` | queue ctor | `(id) => session.annotations.find(id)` (persisted flip) |

These interfaces are the joints: depend on them, not on `WorkspaceManager`, and a
new kind / a fake gateway / a new scene type slots in without touching the rest.
