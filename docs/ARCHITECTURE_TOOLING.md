# Annotation Tooling Architecture — `ui/apps/web`

> **Scope.** This document covers the **annotation tooling** of the workspace app
> (`ui/apps/web`): how a record's annotations are loaded, drawn, edited, rendered
> and saved, and how to add a new annotation kind, tool, renderer or widget. It is
> *not* the app's generic frontend architecture (routing, panels, theming, data
> layer) — for that see `FRONTEND_ARCHITECTURE.md`.
>
> **Status.** Implemented on `refactor/annotation-tools`. The original design
> (Phases 0–6, agreed 2026-06-11) plus the **2026-06-29 plugin-symmetry refactor**
> (Stages 1–5) that brought the 3D pipeline to full parity with 2D, unified the
> commit path, and extracted the shared widget shell. The seams are internal-only
> (D1); they may still change as new kinds harden them.

## Context

The workspace app renders dataset records in widgets (2D image canvas via Konva,
3D point cloud via Threlte/Three.js) and lets users create and edit annotations.
Two kinds exist today — 2D bounding boxes and 3D bounding boxes. The product
direction is many more (mask RLE, polylines, …), so the cost of adding a kind
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
  genuinely new kind end-to-end (mask RLE) before generalizing further.

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
  sceneContext.ts   SceneContextBase, MutationSink, Scene2DReadContext,
                    Scene2DContext, Scene3DContext
  renderer.ts       AnnotationRenderer2D + AnnotationEditor2D (+Factory),
                    AnnotationRenderer3DFactory
  tool.ts           ToolDefinition, DEFAULT_TOOL_2D/3D, Tool2D/ToolHandler2D,
                    Tool3D/ToolHandle3D/AnnotationTool3DProps/ToolHudProps
  registry2d.ts     TOOLS_2D, RENDERER_FACTORIES_2D
  registry3d.ts     TOOLS_3D, RENDERER_FACTORIES_3D
  selectTool2D.ts   kind-agnostic select/delete tool
  scene2dGeometry.ts Konva pixel↔normalized math
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
interface AnnotationRenderer2D { kind; sync(); destroy() }              // display only (read-only ctx)
interface AnnotationEditor2D   { kind; syncSelection(); destroy() }     // input: transformer + commit
interface AnnotationRenderer3DFactory { kind; component: Component<{ ctx: Scene3DContext }> }  // declarative
```

A renderer **pulls** its kind from `ctx.collection.byKind(kind)` and never has data
pushed into it. On 2D, display and input are separate objects (D4): the
`AnnotationRenderer2D` takes a read-only `Scene2DReadContext` (so it *cannot* write
to the queue) and the optional `AnnotationEditor2D` owns the `Konva.Transformer` and
commits — the widget builds both from the same factory. 2D widgets call `sync()` /
`syncSelection()` on change; the 3D scene mounts one component per
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

`TextWidget` calls `buildSeam(manager, …)`, defines `SceneTextContext extends
SceneContextBase` with its own engine handle (the editor/DOM node), and implements
text renderer/tool interfaces mirroring the 2D/3D ones. Everything below the seam —
`AnnotationCollection`, `MutationQueue`, seed loaders, payload builders, the
`commit*` helpers, `buildSeam`, `<AnnotationToolbar>` — is reused unchanged. Per
D10, those text interfaces are written against a real feature, not pre-declared.

### Worked example: a second renderer for an existing kind (bbox3d → 2D projection)

A renderer is **"kind × scene", not just "kind"**: one `bbox3d` annotation has two
renderers — the 3D wireframe (`BBox3DRenderer.svelte`) and a projected 2D wireframe in
the image widget (`kinds/2d/bbox3d/bbox3dRenderer2D.ts`). Because the collection is
record-scoped and `ViewScopedAnnotations` passes record-scoped kinds through every view
filter, the bbox3ds are *already* in the image widget's store; moving a box in 3D
updates the same object, so the projection follows live. Adding this display touched
**no tool, widget, or queue** — it is display-only:

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

## History — the refactor stages

**Phases 0–6 (2026-06-11 design).** 0: mechanical renames (`localBBoxId` →
`localAnnotationId`). 1: `LocalAnnotation` + `AnnotationCollection`. 2: 2D tool
registry. 3: 3D `useBoxEditor` split. 4: payload-builder registry + renderer
interface. 6: record-scoped shared collection on `WorkspaceSession` +
`ViewScopedAnnotations`. **Phase 5 (implement mask RLE end-to-end) is still the
planned validation kind.**

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

- **DEBT-3 — renderer sync tests (partial).** The 2D *editor* now has coverage
  (`bboxEditor2D.test.ts` fires drag/transform → asserts the commit). `bboxRenderer2D.sync()`
  and the 3D Threlte scene still lack node-level tests (need a Konva/Threlte mock
  harness). _Target: alongside the next 2D kind (mask RLE)._

- **DEBT-4 — 3D boxes can't be deleted (this branch).** The point-cloud pipeline
  has no delete path (no Trash button / Delete-key handler / `collection.remove`).
  `deleteLocalAnnotation` already supports `bbox3d` — it is purely unwired. Fix
  needs a UX decision (button vs confirm overlay; confirm-on-delete?). _Target: with
  the next point-cloud UX pass, before GA._

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
  tool can't crash, but the pairing is still by-convention.
  _Target: a typed per-tool session contract when a second 3D tool lands._
