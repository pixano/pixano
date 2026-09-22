# Annotation Tooling Architecture — `ui/apps/web`

> **Scope.** This document covers the **annotation tooling** of the workspace app
> (`ui/apps/web`): how a record's annotations are loaded, drawn, edited, rendered
> and saved, and how to add a new annotation kind, tool, renderer or widget. It is
> *not* the app's generic frontend architecture (routing, panels, theming, data
> layer) — for that see `FRONTEND_ARCHITECTURE.md`.
>
> **Status.** Implemented and in use. The original design (Phases 0–6, agreed
> 2026-06-11) plus the **2026-06-29 plugin-symmetry refactor** (Stages 1–5) that
> brought the 3D pipeline to full parity with 2D, unified the commit path, and
> extracted the shared widget shell. Since then the seams have been exercised by
> four further 2D kinds (mask, keypoints, multi-path, classification) added as
> plugins with no widget, scene or queue edits — the validation D5 asked for. The
> seams are internal-only (D1); they may still change as new kinds harden them.

## Context

The workspace app renders dataset records in widgets (2D image canvas via Konva,
3D point cloud via Threlte/Three.js) and lets users create and edit annotations.
Six kinds exist today: `bbox`, `mask`, `keypoints`, `multi_path` and
`classification` on 2D, and `bbox3d` on 3D (also rendered into image views as a
projection). The product direction is more still, so the cost of adding a kind
must be **one new folder + one registry line per axis**, never edits scattered
across existing widgets or scenes.

### What already worked (and is kept)

| Layer | Mechanism | Why it stays |
|---|---|---|
| Widget types | `WidgetExtension.create()` registry (TipTap-style) | Already open/closed at the widget level |
| Data access | `DatasetGateway` / `MutationGateway` narrow interfaces | DIP-friendly; the queue depends on the smallest surface |
| Save pipeline | `MutationQueue` (ordered flush: entities → annotations, deletes last) | Kind-agnostic core; the persisted-flip happens here |
| Record loading | `addRecordSeed` claim mechanism + per-kind `SEED_LOADERS` | Extensions claim (record, view) pairs; loaders map REST→local once per record |

## Decisions

Original design (2026-06-11):

- **D1 — Tool plugin layer, internal-only.** Tools/renderers are plugins in
  registries. The API is for in-repo tools; interfaces stay lean and may change.
- **D2 — Single-frame scope.** The local model covers single-image / single-point-
  cloud records. Video (tracklets, per-frame state) is out of scope. Payload
  builders keep `frame_id = view_id`.
- **D3 — No universal tool interface across 2D and 3D.** Konva hit-testing and
  Three.js raycasting are too different to force one pointer abstraction. The two
  scene families share only the metadata type (`ToolDefinition`) and the
  medium-agnostic seam (`SceneContextBase`).
- **D4 — Renderers are separate from tools (ISP).** Displaying persisted
  annotations must work with no tool active; input is a different responsibility.
- **D5 — Validation by construction.** Seams are proven by implementing a
  genuinely new kind end-to-end before generalizing further. _Discharged:_ mask
  RLE landed as the first validation kind, followed by keypoints, multi-path and
  classification — all as folder + registry lines.

2026-06-29 refactor:

- **D6 — 3D renderers and tool overlays are Svelte components.** Threlte rendering
  *is* declarative markup, so the natural plugin unit in 3D is a component (it emits
  `<T.*>` nodes), not an imperative `sync()` object as in 2D. Registries hold the
  component; the scene mounts it.
- **D7 — The widget owns the seam; the scene finishes the context.** The widget
  builds the medium-agnostic `SceneContextBase` (scoped collection + mutation sink
  + tool switcher). A 2D widget completes it into `Scene2DContext` once its Konva
  stage exists; the 3D **scene** completes it into `Scene3DContext` because the
  camera and OrbitControls only exist inside the Threlte `<Canvas>`.
- **D8 — The scene names no kind; kind-specific host I/O is forwarded opaquely.**
  bbox3d-specific widget inputs (gizmo visibility, confirm/cancel callbacks) are
  bundled by the widget under the tool id and forwarded by the scene as an opaque
  `toolProps[toolId]` bag — they never appear on the generic `Scene3DContext`.
- **D9 — One commit path, reusing `buildUpdate` as the draft patch.**
  `commitNewAnnotation` / `commitGeometryEdit` serve every kind. The edit path uses
  the kind's `buildUpdate` body to patch a still-pending create, because the create
  body is a superset of the update body's geometry fields — so patching changes
  only the geometry.
- **D10 — Text-readiness is structural, not speculative (YAGNI).** The
  medium-agnostic spine + `buildSeam` are the proven universal entry point. A new
  medium's interfaces (`SceneTextContext`, a text renderer/tool) are built against a
  real text-annotation feature, not pre-declared as dead abstractions.

## Architecture (implemented)

### 1. One local annotation model

```ts
interface LocalAnnotation<G = unknown> {
  id: string;
  entityId: string;
  kind: AnnotationKind;     // "bbox" | "bbox3d" | "mask" | …
  viewId: string;           // the view row it belongs to ("" for record-scoped kinds)
  geometry: G;              // per-kind shape, typed in the kind's module
  persisted: boolean;       // false = draft (create still queued)
  entity?: Record<string, unknown>;
}
```

Optimistic edits mutate `geometry` in place; the pending mutation queue is the
ledger of unsaved changes. A single **record-scoped** `AnnotationCollection`
(`.svelte.ts` runes class) lives on `WorkspaceSession.annotations` — one instance
per loaded record, shared by every widget viewing it (so moving a 3D box updates
its 2D projection live, and two widgets never diverge). Image widgets see the
record through a `ViewScopedAnnotations` facade that filters to their view plus
`RECORD_SCOPED_KINDS` (e.g. `bbox3d`); writes pass through to the one collection.

### 2. The `scene/` contracts (shared seam)

`lib/annotations/scene/` holds everything tools, renderers and widgets program
against — the medium-agnostic contracts, the registries, and the kind-agnostic
select tool. (It was renamed from `tools/` in the 2026-06-29 refactor; it is not
"just tools" — it is the whole scene/render/tool contract.)

```
scene/
  sceneContext.ts   SceneContextBase, MutationSink, LiveAnnotationDraft,
                    LiveDraftSource / LiveDraftChannel, Scene2DReadContext,
                    Scene2DContext, Scene3DContext
  toolDefinition.ts ToolDefinition — the metadata 2D and 3D tools share (D3)
  renderer.ts       AnnotationRenderer2D + AnnotationEditor2D (+Factory),
                    AnnotationRenderer3DFactory
  tool.ts           DEFAULT_TOOL_2D/3D, Tool2D/ToolHandler2D,
                    Tool3D/ToolHandle3D/AnnotationTool3DProps/ToolHudProps
  registry2d.ts     TOOLS_2D, RENDERER_FACTORIES_2D
  registry3d.ts     TOOLS_3D, RENDERER_FACTORIES_3D
  selectTool2D.ts   kind-agnostic select/delete tool
  flatCoordsEditor2D.ts  shared vertex editor reused by keypoints and multi-path
  entityLabels2D.ts      shared entity-label rendering
  scene2dGeometry.ts     Konva pixel↔normalized math
  scene2dStyleConstants.ts  shared 2D draw styling
```

**`SceneContextBase`** is the seam every medium shares:

```ts
interface SceneContextBase {
  widgetId: string;
  buildContext: BuildContext;
  collection: AnnotationStore;   // view-scoped window onto the shared collection
  mutations: MutationSink;
  setActiveTool(id: string): void;
  requestRedraw(): void;
}
```

`Scene2DContext` adds the Konva handles (`stage`, `annotationLayer`,
`getKonvaImage`); `Scene3DContext` adds the Threlte engine handles (`camera`,
`getControls`, `floorY`, `cameraTarget`, `orbitCenterDist`, `activeToolId`,
`editingId`). Tools and renderers depend on these interfaces — **never** on the
widget or `WorkspaceManager` directly.

Two host helpers (`lib/components/widgets/sceneSeam.ts`) remove all per-widget
duplication of seam wiring:

- `buildMutationSink(manager)` → the `MutationSink` forwarding to the queue.
- `buildSeam(manager, { widgetId, buildContext, storage, requestRedraw? })` →
  the full `SceneContextBase`. **This is the single entry point a new medium
  reuses** — it never re-implements collection wiring or mutation plumbing.

The toolbar is shared too: `components/widgets/AnnotationToolbar.svelte` (tool
buttons + pending/save) with a `controls` snippet for widget-specific buttons
(delete for image, camera-mode for point cloud).

### 3. Tool registries (per scene type)

```ts
interface ToolDefinition { id; label; icon; kind?; cursor? }            // shared metadata

interface Tool2D extends ToolDefinition {                              // 2D: imperative handler
  createHandler(ctx: Scene2DContext): ToolHandler2D                    // activate/onPointer*/onKeyDown
}

interface Tool3D extends ToolDefinition {                              // 3D: kind-owned pieces
  overlay?: Component<AnnotationTool3DProps>       // in-canvas editor + transient preview
  createSession?: (seam) => unknown                // per-widget confirm state + commit
  hud?: Component<ToolHudProps>                     // DOM confirm/secondary UI
}
interface ToolHandle3D { activeDragging: boolean; editingId: string | null }
```

- **2D:** the widget swaps the active `ToolHandler2D` on tool change and routes
  Konva pointer events to it. "Select/edit" is itself a tool (`selectTool2D`).
- **3D:** an editing tool carries three kind-owned pieces the host wires
  generically — `overlay` (in-canvas editor + gizmos; the editor lives here because
  its `$effect`s need a component scope), `createSession` (a per-widget session
  holding confirm state, gizmo visibility and the commit), and `hud` (the DOM
  confirm panel driven by that session). The scene mounts overlays and stores each
  tool's `ToolHandle3D` by id (camera reads `activeDragging`, renderers skip
  `editingId`); the widget mounts the active tool's HUD. The navigate tool has none.
  (This is why `PointCloudWidget` names no kind — resolving DEBT-2 and DEBT-5.)

### 4. Renderer registries (per kind, per scene type)

```ts
interface AnnotationRenderer2D { kind; sync(); syncDraft(draft); destroy() }  // display only (read-only ctx)
interface AnnotationEditor2D   { kind; syncSelection(); destroy() }           // input: transformer + commit
interface AnnotationRenderer3DFactory { kind; component: Component<{ ctx: Scene3DContext }> }  // declarative
```

A renderer **pulls** its kind from `ctx.collection.byKind(kind)` and never has data
pushed into it. On 2D, display and input are separate objects (D4): the
`AnnotationRenderer2D` takes a read-only `Scene2DReadContext` (so it *cannot* write
to the queue) and the optional `AnnotationEditor2D` owns the `Konva.Transformer` and
commits — the widget builds both from the same factory. 2D widgets call `sync()` /
`syncSelection()` on change, and `syncDraft()` on every live-draft change (see the
live-projection note in the worked example: `sync()` is proportional to the
collection, `syncDraft()` must stay proportional to the draft); the 3D scene mounts one component per
`RENDERER_FACTORIES_3D` entry and Svelte reactivity redraws it. The scene names no
kind in either case.

### 5. Payload builders + generic commit

```ts
interface PayloadBuilder<G> { kind; resource;
  buildCreate(ctx, ann, widgetId): ResourceMutation[];
  buildUpdate(ctx, ann): Record<string, unknown> }
```

`PAYLOAD_BUILDERS` maps kind → builder; `SEED_LOADERS` is the REST→local mirror.
Two kind-agnostic helpers (`lib/annotations/payloadBuilders.ts`) own the whole
draft/edit lifecycle so no tool, renderer or widget reaches into payload internals:

- `commitNewAnnotation(ctx, kind, geometry, ids?)` — add a draft (`persisted:false`)
  to the collection and queue its creates.
- `commitGeometryEdit(ctx, annotationId, geometry)` — write the edit, then queue an
  `update` (persisted) or patch the pending create (draft) using `buildUpdate` (D9).

Both take a `CommitContext` (`{ buildContext, collection, mutations, widgetId }`)
which both `Scene2DContext` and the widgets' seam satisfy.

### Adding a new annotation kind (the recipe)

1. Add the kind literal to `AnnotationKind` and its geometry to `GeometryByKind`
   in `lib/annotations/annotationCollection.svelte.ts`.
2. Create `lib/annotations/kinds/<2d|3d>/<kind>/` with:
   - `<kind>PayloadBuilder.ts` — local→REST (resource + create/update bodies),
   - `<kind>SeedLoader.ts` — REST→local (fetch + map the record's rows once),
   - the **renderer** (display): `<kind>Renderer2D.ts` (`AnnotationRenderer2D`,
     read-only ctx) **or** `<Kind>Renderer.svelte` (3D component reading `ctx.collection`),
   - the **editing input**: 2D → `<kind>Editor2D.ts` (`AnnotationEditor2D`) exposed
     via the factory's `createEditor`; 3D → a `<Kind>Tool.svelte` overlay on
     `Tool3D.overlay`, plus (if it needs a confirm step) a `createSession` + a `hud`,
   - the **toolbar tool**: `draw<Kind>Tool.ts` (`Tool2D` with `createHandler`, or a
     `Tool3D` entry).
3. Register one line each: `PAYLOAD_BUILDERS`, `SEED_LOADERS`, and the per-scene
   `RENDERER_FACTORIES_*` / `TOOLS_*` in `scene/registry2d.ts` / `registry3d.ts`.
4. Use `commitNewAnnotation` / `commitGeometryEdit` for the write-path — never
   hand-build mutations in the tool/renderer/widget.
5. Tests: builder unit tests + a tool-lifecycle test through a fake context (see
   `scene/__tests__/selectTool2D.test.ts`).
6. **Nothing else changes** — no widget edits, no scene edits, no queue edits.

### Adding a new medium (e.g. text)

> A `TextWidget.svelte` already exists (registered via `TextExtension`), but it is a
> **display-only Tiptap host**: it calls no `buildSeam`, defines no scene context and
> carries no renderer or tool. It is not an instance of what follows — text
> *annotation* is still unbuilt.

An annotating text widget would call `buildSeam(manager, …)`, define
`SceneTextContext extends SceneContextBase` with its own engine handle (the
editor/DOM node), and implement text renderer/tool interfaces mirroring the 2D/3D
ones. Everything below the seam —
`AnnotationCollection`, `MutationQueue`, seed loaders, payload builders, the
`commit*` helpers, `buildSeam`, `<AnnotationToolbar>` — is reused unchanged. Per
D10, those text interfaces are written against a real feature, not pre-declared.

### Worked example: a second renderer for an existing kind (bbox3d → 2D projection)

A renderer is **"kind × scene", not just "kind"**: one `bbox3d` annotation has two
renderers — the 3D wireframe (`BBox3DRenderer.svelte`) and a projected 2D wireframe in
the image widget (`kinds/2d/bbox3d/bbox3dRenderer2D.ts`). Because the collection is
record-scoped and `ViewScopedAnnotations` passes record-scoped kinds through every view
filter, the bbox3ds are *already* in the image widget's store; moving a box in 3D
updates the same object, so a **saved** edit re-projects with no extra plumbing.
Adding the display touched **no tool, widget, or queue** — it is display-only:

1. `kinds/2d/bbox3d/bbox3dRenderer2D.ts` implements `AnnotationRenderer2D`
   (`kind: "bbox3d"`, read-only `Scene2DReadContext`). `sync()` reads
   `ctx.collection.byKind("bbox3d")`, projects each box's 8 corners through the camera
   calibration, and draws Konva lines via `getPixelFrame` (`scene2dGeometry.ts`).
2. Registered in `RENDERER_FACTORIES_2D` (`scene/registry2d.ts`).
3. The one seam it needed: a `camera` field on `Scene2DReadContext`
   (`{ imageWidth, imageHeight, calibration }`), populated by `ImageWidget` from
   `options` (plumbed by `ImageExtension`).
4. The projection math mirrors the backend `src/pixano/schemas/annotations/bbox.py`
   (`get_3dbbox_corners`, `project_points`): the 8 corners of a unit cube × size ×
   rotation + center, then extrinsics → perspective divide → intrinsics.

**Live projection (2026-07-30) — where "display-only" stopped being true.** The
paragraph above holds for *committed* geometry. Previewing a gesture **while it is
still in the pointer's hand** is a different problem: the in-flight box is not in the
collection at all (the store contract covers committed annotations — membership,
selection, deletion), so there was nothing for the image widget to re-project. That
needed a real seam addition, not just a renderer:

1. `LiveAnnotationDraft` + a `liveDraft` slot on `WorkspaceSession`, exposed through
   `SceneContextBase` as a read/write `LiveDraftChannel` and to renderers as a
   read-only `LiveDraftSource` (D4: a renderer still cannot publish).
2. `AnnotationRenderer2D.syncDraft(draft)` — a **required** second entry point.
   `sync()` reconciles the whole collection; `syncDraft` reconciles only the preview
   and runs at pointer rate, so it must stay proportional to the draft, never to the
   collection. `ImageWidget` splits its effect accordingly: structural changes take
   the full reconcile, the draft takes the narrow path. Required rather than optional
   so a renamed or mistyped implementation is a compile error, not a silent opt-out;
   kinds with no cross-widget preview implement a documented no-op.
3. The 3D tool publishes on every editor change (`BBox3DSession.reportPreview`) and
   clears on gesture end/unmount — clearing only a draft it owns, since the slot is
   shared workspace-wide.

The lesson for the next kind: **cross-widget *live* feedback is a seam feature, not a
renderer feature.** A renderer alone can mirror committed state; it cannot see a
gesture happening in another medium.

## History — the refactor stages

**Phases 0–6 (2026-06-11 design).** 0: mechanical renames (`localBBoxId` →
`localAnnotationId`). 1: `LocalAnnotation` + `AnnotationCollection`. 2: 2D tool
registry. 3: 3D `useBoxEditor` split. 4: payload-builder registry + renderer
interface. 6: record-scoped shared collection on `WorkspaceSession` +
`ViewScopedAnnotations`. 5: mask RLE end-to-end — **shipped**, and with it the D5
validation the seams were waiting on.

**2026-06-29 plugin-symmetry refactor (Stages 1–5).** Brought 3D to full parity
with 2D and removed the last duplications. Each stage shipped with `pnpm run
check` at baseline error count and `vitest` green:

| Stage | Content |
|---|---|
| 1 | `tools/` → `scene/` rename; split contracts into `sceneContext.ts` / `renderer.ts` / `tool.ts`; introduce `SceneContextBase` |
| 2 | 3D renderer plugin: `AnnotationRenderer3DFactory` + `RENDERER_FACTORIES_3D`; extract `BBox3DRenderer.svelte` (pulls from the collection); drop the `bboxes3d` prop; `buildMutationSink` |
| 3 | 3D tool plugin: `Tool3D.overlay` + `ToolHandle3D` + `Scene3DContext` engine handles; extract `BBox3DTool.svelte` (editor + preview); scene mounts overlays from the registry; opaque `toolProps` forwarding (D8). _Currently one overlay tool only — see DEBT-6._ |
| 4 | Generic commit: `commitNewAnnotation` / `commitGeometryEdit` replace four bespoke save sites (D9); unit-tested in `__tests__/commit.test.ts` |
| 5 | Shared shell: `buildSeam` + `<AnnotationToolbar>` adopted by both widgets |

> **Verification note.** The 3D editor interaction has no automated tests (the
> suite covers loaders/builders/queue/seeds, not the Threlte scene). Stage 3 moved
> the editor and its markup verbatim into `BBox3DTool.svelte`; behaviour rests on
> that move plus manual verification (draw / move / resize / rotate / orbit-lock /
> save). This overlaps DEBT-3.

## Non-goals

- Video / tracklet support (D2).
- A public, semver-stable plugin API (D1).
- Changing the backend API, the widget extension registry, or the mutation-queue
  flush semantics.

## Known debts (tracked)

- **DEBT-1 — ~~bbox edit input lives in the renderer~~ → RESOLVED (2026-07-01, review A4).**
  `bboxRenderer2D.ts` now receives a read-only `Scene2DReadContext` (no `mutations`,
  no `setActiveTool`), so a renderer physically cannot write to the queue. The
  `Konva.Transformer` + drag/transform → commit moved to `bboxEditor2D.ts`
  (implements `AnnotationEditor2D`, uses layer-delegated events), wired by the widget
  from `AnnotationRenderer2DFactory.createEditor`. Display and input are now separate
  by construction (D4). Covered by `bboxEditor2D.test.ts`.

- **DEBT-2 — ~~3D write-path lives in `PointCloudWidget`~~ → RESOLVED (2026-06-29).**
  Stage 3 introduced `Scene3DContext` + `Tool3D.overlay`, moving the editor and the
  bbox3d write-path into the kind module (`BBox3DTool.svelte` +
  `commit*` helpers). Adding a 3D kind no longer needs widget surgery. _Residual
  resolved 2026-07-01 (DEBT-5): the confirm UI + save orchestration also left the widget._

- **DEBT-3 — renderer sync tests (partial → mostly resolved for 2D, 2026-07-30).**
  The 2D *editor* has coverage (`bboxEditor2D.test.ts` fires drag/transform → asserts
  the commit). `bbox3dRenderer2D` now has node-level tests too
  (`bbox3dRenderer2D.test.ts`): projection math against hand-computed
  pixels, per-box independence of the shared scratch buffers, create/destroy
  lifecycle, entity-visibility filtering, degraded inputs (no calibration / no loaded
  image), rotation, and the whole `syncDraft` fast path including its gesture
  start/end transitions. The suite is mutation-checked — removing the visibility
  check, the rotation matrix, the scratch indexing or the draft-visibility guard each
  turns it red. **The blocker is gone:** the "Konva mock harness" that debt was
  waiting on now exists (a `vi.mock("konva")` fake `Line` plus a parameterisable
  `Scene2DReadContext`), so covering `bboxRenderer2D.sync()` was a copy-and-adapt job
  — **done**: `bboxRenderer2D.test.ts` exists, and every 2D kind added since ships its
  own renderer test (`maskRenderer2D`, `keypointsRenderer2D`, `multiPathRenderer2D`,
  `classificationEditor2D`).
  _Remaining: the 3D Threlte scene only — it still needs a Threlte harness, a
  genuinely separate problem. Target: with the next point-cloud UX pass._

- **DEBT-7 — 3D boxes can't be selected from an image view (2026-07-30).** The
  projected wireframes are display-only: they carry no click handler, and
  `bbox3dRenderer2DFactory` has no `createEditor`, so nothing ever puts a bbox3d id
  in `collection.selectedId`. `bbox3dRenderer2D` used to build a `Konva.Transformer`
  for that selection; it was **unreachable code** (the lookup was keyed by bbox3d id
  against a `selectedId` only ever holding 2D bbox ids) and was deleted rather than
  left to mislead — it had already cost one round of debugging in `d5e3e505`. The
  wireframes are now `listening: false`, since a listening line with no handler could
  only swallow `selectTool2D`'s click-empty-canvas-to-deselect.
  Wiring selection up means: a click handler + `listening: true` on the **persisted**
  lines only (never the live draft, which mirrors another widget's in-flight gesture),
  and a UX decision on what "selected" does — a `Konva.Transformer` is the wrong
  affordance, since resizing a perspective-projected 8-corner shape has no
  well-defined mapping back to a 3D edit. Highlight-only is the plausible version.
  _Target: with the next point-cloud UX pass, alongside DEBT-4._

- **DEBT-4 — ~~3D boxes can't be deleted~~ → RESOLVED (#662), narrowed 2026-07-30.**
  The delete path shipped in `f57f59a2` *"link entities to 2D/3D boxes (deferred
  entity, reassign, delete)"*: `BBox3DSession.deleteBox()` routes through the shared
  `deleteLocalAnnotation` (queueing a delete for a saved box, dropping the pending
  creates for an unsaved one) and is wired to a Delete button in `BBox3DHud.svelte`.
  `deleteBox()` and `changeEntity()` shipped untested; both are now covered in
  `bbox3dSession.test.ts` (2026-07-30).
  _Residual, all UX rather than plumbing:_
  - **No keyboard delete in the point cloud.** `selectTool2D` handles
    `Delete`/`Backspace` for 2D only; the 3D scene has no equivalent.
  - **No confirmation step.** The original debt asked for that call ("button vs
    confirm overlay; confirm-on-delete?"); the button deletes immediately. The
    mutation is queued rather than flushed, so it is recoverable until save — but
    nothing tells the user that.
  - **Discoverability.** Delete is reachable *only* through the edit-confirm HUD:
    you must click a box to enter the `confirming` phase. There is no delete from a
    selection, from the entities panel, or from the toolbar.

  _Target: with the next point-cloud UX pass, alongside DEBT-7._

- **DEBT-5 — ~~PointCloudWidget owns bbox3d UI + save orchestration~~ → RESOLVED
  (2026-07-01, review A1).** The confirm state, gizmo visibility and commit moved into
  a kind-owned `BBox3DSession` (`bbox3dSession.svelte.ts`, unit-tested) plus a DOM HUD
  (`BBox3DHud.svelte`), wired via `Tool3D.createSession` + `Tool3D.hud`.
  `PointCloudWidget` now only creates each tool's session and routes it to the scene
  overlay + HUD — it names no kind and builds no bbox3d payload. The editor reports
  drafts into the session; the HUD drives save/cancel/gizmo out of it.

- **DEBT-6 — 3D multi-tool handle (RESOLVED 2026-07-01, A2); typed host↔tool
  contract (partial, A3).** A2 is fixed: `PointCloudScene` keys handles by tool id
  (`toolHandles[tool.id]`, set via a `reportHandle` callback) and reads the active
  tool's handle, so a second overlay tool can no longer clobber the first. A3 remains
  reduced-but-present: the tool's session/props still travel as `unknown` through
  `toolProps` / `ToolHudProps` (the host is a deliberately kind-agnostic courier). The
  HUD mount is now guarded (`sessions[tool.id]` truthy) so a `hud`-without-`createSession`
  tool can't crash, but the pairing is still by-convention. **The guard covers session
  *absence*, not session *type*:** `BBox3DHud` and `BBox3DTool` both downcast
  (`rawSession as BBox3DSession`) with no runtime check, and `BBox3DTool` declares
  `session?: BBox3DSession` optional while using it as required — so a mismatched
  `hud`/`createSession` pairing is still a runtime crash, not a compile error.
  _Target: a typed per-tool session contract when a second 3D tool lands._
