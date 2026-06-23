# Annotation Tooling Architecture — `ui/apps/web`

> Status: agreed design, 2026-06-11. Scope: the next-UI workspace app (`ui/apps/web`).
> Drives the refactoring on `refactor/annotation-tools` and all future annotation tools
> (mask RLE, polylines, …).

## Context

The workspace app renders dataset records in widgets (2D image canvas via Konva,
3D point cloud via Threlte/Three.js) and lets users create and edit annotations.
Today two annotation kinds exist — 2D bounding boxes and 3D bounding boxes — and
their logic is baked directly into the widgets. The product direction is to add
many more annotation kinds (mask RLE, polylines, …), so the cost of
adding a kind must be **one new module + one registration**, not edits scattered
across existing widgets.

### What already works (and is kept)

| Layer | Mechanism | Why it stays |
|---|---|---|
| Widget types | `WidgetExtension.create()` registry (TipTap-style) | Already open/closed at the widget level |
| Data access | `DatasetGateway` / `MutationGateway` narrow interfaces | DIP-friendly; queue depends on the smallest surface |
| Save pipeline | `MutationQueue` (ordered flush, entities-before-annotations, deletes last) | Kind-agnostic core; only its *naming* leaks bbox specifics |
| Record loading | `addRecordSeed` claim mechanism | Lets extensions claim (record, view) pairs without central dispatch |

### The problems (why this refactoring exists)

1. **Tools are not a concept.** `ImageWidget.svelte` hard-codes its toolbar, the
   mode union (`"select" | "draw-bbox"`), and per-mode event routing. Every new
   tool widens unions and adds branches in existing files (OCP violation).
2. **Three representations of one concept.** `LocalBBox` (2D), `DraftBBox3D` plus
   a separate `overrides` map (3D) all model "a local annotation with optimistic
   state". The draft → queue → persisted-flip → optimistic-edit lifecycle is
   duplicated with diverging shapes.
3. **Bbox naming leaks into generic infrastructure.** `ResourceMutation.localBBoxId`,
   `LocalBBoxLocator`, `findLocalDraft` are generic in semantics but bbox-specific
   in name/type.
4. **Payload builders are a closed set.** `buildBBoxCreate` / `buildBBox3DCreate`
   are near-duplicates; each kind would add another copy.
5. **SRP strain.** `useBoxEditor.svelte.ts` mixes raycasting services, gizmo
   geometry, a drag state machine, and draft/override bookkeeping.

## Decisions

- **D1 — Tool plugin layer, internal-only.** Tools are plugins registered in a
  tool registry. The API is for in-repo tools only: interfaces stay lean and may
  change freely. A public extension API can be carved out later once 3–4 tools
  have hardened the contracts.
- **D2 — Single-frame scope.** The local annotation model covers single-image /
  single-point-cloud records. Video (tracklets, per-frame state) is explicitly
  out of scope; it will be designed on top of these seams when it lands. Payload
  builders keep `frame_id = view_id` as today.
- **D3 — No universal tool interface across 2D and 3D.** Konva hit-testing and
  Three.js raycasting are too different; forcing one pointer abstraction would be
  over-engineering. Two small parallel interfaces share only the metadata type.
- **D4 — Renderers are separate from tools (ISP).** Displaying persisted
  annotations must work with no tool active; input handling is a different
  responsibility from rendering.
- **D5 — Validation by construction.** The seams are proven by implementing a
  genuinely new kind end-to-end before generalizing further. Mask RLE is the
  planned next kind and the hardest case (RLE codecs, brush/polygon input,
  compositing).

## Target architecture

### 1. One local annotation model

Replaces `LocalBBox`, `DraftBBox3D` and the 3D `overrides` map:

```ts
interface LocalAnnotation<G = unknown> {
  id: string;
  entityId: string;
  kind: AnnotationKind;     // "bbox" | "bbox3d" | "mask" | …
  geometry: G;              // per-kind shape, typed in the kind's module
  persisted: boolean;
  entity?: Record<string, unknown>;
}
```

> Amendment (Phase 1): the originally planned `draftGeometry` field was dropped.
> Optimistic edits mutate `geometry` in place and the pending mutation queue is
> the ledger of unsaved changes — exactly how the 2D widget already behaved.
> The 3D `overrides` map becomes unnecessary once persisted boxes live in the
> collection instead of immutable widget `data`.

A single `AnnotationCollection` (`.svelte.ts` runes class) owns: the annotation
list, selection, the persisted flip after a successful create, optimistic edits,
and delete-with-pending-mutation-drop.

> Amendment (Phase 6): the collection is **record-scoped, not widget-scoped**.
> One instance lives on `WorkspaceSession.annotations` per loaded record;
> every widget reads and writes the same one (so moving a 3D box updates its
> 2D projection live, and two widgets can never hold diverging copies or queue
> duplicate mutations for the same annotation). `LocalAnnotation` carries a
> `viewId`; image widgets see the record through a `ViewScopedAnnotations`
> facade that filters to their view plus record-scoped kinds
> (`RECORD_SCOPED_KINDS`, e.g. `bbox3d`). Selection is shared — selecting an
> annotation in one widget highlights it everywhere. Per-widget storage keeps
> only genuinely per-widget state (`activeToolId`).

### 2. Tool registry (per scene type)

```ts
interface ToolDefinition { id: string; label: string; icon: ComponentType; kind?: AnnotationKind; cursor?: string }
interface Tool2D extends ToolDefinition { createHandler(ctx: Scene2DContext): ToolHandler2D }
type Tool3D = ToolDefinition  // metadata-only: 3D pointer handling lives in the scene's BoxEditor (see D3 / "Known debts")
```

- `ToolHandler*` exposes `activate / deactivate / onPointerDown / onPointerMove /
  onPointerUp` and receives a `commit(geometry)` callback.
- `Scene2DContext` wraps the Konva stage (pixel↔normalized transforms, layer
  access); `Scene3DContext` wraps camera + raycasting services.
- Widgets render their toolbar from the registry (`toolRegistry.for("2d")`) and
  delegate pointer events to the active handler. Widgets contain **no tool-specific
  branches**.
- "Select/edit" is itself a tool (the default one), so editing gizmos live in
  tool handlers, not in widgets.

### 3. Renderer registry (per kind, per scene type)

```ts
interface AnnotationRenderer2D { kind: AnnotationKind; sync(scene: Scene2DContext, anns: LocalAnnotation[]): void; hitTest?(…): string | null }
```

The existing `BBoxAnnotationLayer` becomes the first 2D renderer behind this
interface; a generic annotation-layer host in each widget iterates registered
renderers for the kinds present in the collection.

### 4. Payload builder registry

```ts
interface PayloadBuilder<G> { kind: AnnotationKind; resource: string;
  buildCreate(ctx: BuildContext, ann: LocalAnnotation<G>): ResourceMutation[];
  buildUpdate(ctx: BuildContext, ann: LocalAnnotation<G>): Record<string, unknown> }
```

`buildBBoxCreate` / `buildBBox3DCreate` become the first two entries. Mutation
metadata is renamed: `localBBoxId` → `localAnnotationId`, `LocalBBoxLocator` →
`LocalAnnotationLocator` (semantics unchanged).

### Adding a new annotation kind (the recipe)

1. Add the kind literal to `AnnotationKind` and its geometry type in
   `lib/annotations/annotationCollection.svelte.ts`.
2. Create `lib/annotations/kinds/<2d|3d>/<kind>/` with:
   - `<kind>PayloadBuilder.ts` — local→REST: resource name + create/update bodies,
   - `<kind>SeedLoader.ts` — REST→local: fetch the record's rows once and map
     them (the other half of the builder symmetry),
   - `<kind>Renderer2D.ts` — displays the kind on the scene (implements
     `AnnotationRenderer2D`),
   - `draw<Kind>Tool.ts` — creation input (implements `Tool2D`).
3. Register: the builder in `lib/annotations/payloadBuilders.ts`
   (`PAYLOAD_BUILDERS`), the seed loader in `lib/annotations/seedLoaders.ts`
   (`SEED_LOADERS`), the renderer and tool in
   `lib/annotations/tools/registry2d.ts` (`RENDERER_FACTORIES_2D`, `TOOLS_2D`).
4. Tests: builder unit tests + one tool-lifecycle test through a fake
   `Scene2DContext` (see `tools/__tests__/selectTool2D.test.ts`).
5. In the renderer's `sync()`, honour **entity-driven visibility** with one guard
   atop the reconcile loop — `if (ann.persisted && !ctx.isEntityVisible(ann.entityId)) continue;`
   — so a hidden entity's annotations produce no scene node (invisible AND
   non-interactive); drafts (not yet persisted) always show. The filter is
   record-scoped shared state on `WorkspaceSession` (`visibleEntityIds`,
   `null` = all), driven by the Entities panel — a uniform, entity-id-based
   display filter, never per-kind.
6. Nothing else changes: no widget edits, no mode-union edits, no queue edits.

> Closed gap: loading persisted annotations is now the per-kind
> `SEED_LOADERS` registry — the REST→local mirror of the payload builders.
> Extensions only describe the view they claim (`seed.view`: row id, logical
> name, media dimensions); `RecordLoader` indexes the claimed views and runs
> every kind's loader **once per record** (previously each image view
> re-fetched the record's bboxes), merging the results into the shared
> collection. Extensions contain zero annotation-mapping code.

## Migration plan

Each phase ships independently with tests green.

| Phase | Content |
|---|---|
| 0 | Mechanical renames: `localBBoxId` → `localAnnotationId`, `LocalBBoxLocator` → `LocalAnnotationLocator` |
| 1 | `LocalAnnotation` + `AnnotationCollection`; migrate both widget storages (3D `overrides` → `draftGeometry`) |
| 2 | Tool registry + 2D refactor: "select" and "draw-bbox" become the first `Tool2D` plugins; toolbar data-driven |
| 3 | 3D refactor: split `useBoxEditor` into `Scene3DContext` services + box-edit tool + box-draw tool |
| 4 | Payload-builder registry + renderer interface; write the "add a tool" recipe |
| 5 | Implement a new kind (mask RLE) end-to-end as validation of the seams |
| 6 | Record-scoped shared `AnnotationCollection` on `WorkspaceSession`; `viewId` on the model; `ViewScopedAnnotations` facade; seeds contribute annotation arrays merged (deduplicated) by `RecordLoader`; `findLocalDraft` hook removed |

## Non-goals

- Video / tracklet support (D2).
- A public, semver-stable plugin API (D1).
- Changing the backend API, the widget extension registry, or the mutation queue
  flush semantics.

## Known debts (tracked)

Accepted weaker designs that **must be fixed later** — recorded here so the
deviation is intentional, not forgotten (raised in the 2026-06-19 code review).

- **DEBT-1 (was B1/S5) — bbox edit input lives in the renderer.**
  `kinds/2d/bbox/bboxRenderer2D.ts` owns the `Konva.Transformer` + draggable
  rects and commits geometry on drag/transform, so a *renderer* writes to the
  collection and queue — contradicting D4 ("tools write, renderers read").
  Fix: move the transformer + drag/transform-commit into the select tool (or a
  shared edit controller), and hand renderers a **read-only** sub-interface of
  `Scene2DContext` (no `mutations`/`setActiveTool`) so the leak is impossible by
  construction. Deferred: the 2D edit interaction has no unit coverage yet, so
  restructuring it is paired with DEBT-3. _Target: before the next 2D kind
  (mask RLE) lands._

- **DEBT-2 (was B3) — 3D write-path lives in `PointCloudWidget`.**
  The widget builds bbox3d payloads, mutates the collection, and patches pending
  mutations inline, so the 3D widget is a host **and** the bbox3d transport (a
  host-not-tool / SRP break), and the 3D pipeline is not open/closed: adding a
  3D kind needs widget surgery. Fix: introduce `Scene3DContext` + a `Tool3D`
  handler factory (mirroring `Tool2D`) and move the write-path into the
  bbox3d kind module. _Target: when the second 3D kind is added (the
  trigger already noted in `tools/types3d.ts`)._
  Update (entity-assignment feature): the new-box entity-commit also lives in
  `PointCloudWidget` (it assembles a `DraftCommitContext` from the manager and
  calls the shared `commitDraftWithEntity`). The commit logic itself is now
  kind-agnostic; only the manager-vs-`Scene3DContext` wiring remains for this
  fix to absorb.

- **DEBT-3 (was T1) — no renderer sync tests.** `bboxRenderer2D` (and the 3D
  gizmo rendering) have no `sync()` tests; renderer-in-node testing needs a
  Konva/Threlte mock harness. Fix: add a fake-`Scene2DContext` + mocked-Konva
  harness and cover `sync()` reconcile/selection. _Target: alongside DEBT-1._

- **DEBT-4 (2026-06-22 review) — 3D boxes can't be deleted.** The point-cloud
  pipeline has no delete path: `PointCloudWidget` / `boxEditor` /
  `PointCloudScene` have no Trash button, no Delete/Backspace handler, and never
  call `collection.remove`. 2D deletes via `deleteLocalAnnotation` (select tool
  + widget button); the helper already supports `bbox3d` (`payloadBuilderFor`
  covers the kind) — it is purely unwired. Fix: wire a 3D delete (button +
  Delete key) through `deleteLocalAnnotation`. Deferred because it needs a UX
  decision (button placement vs the confirm overlay; confirm-on-delete?), best
  made deliberately rather than bolted on. _Target: with the next point-cloud
  UX pass, before GA._

- **DEBT-5 (2026-06-23 review) — entity-visibility is opt-in per renderer.** The
  entity-driven display filter (`isEntityVisible`) is applied by a hand-written
  guard in each read path — `bboxRenderer2D.sync()` and
  `PointCloudWidget.allBboxes3d` — rather than enforced by the store the way
  view-scoping is (`ViewScopedAnnotations._visible`). A future kind's renderer
  that omits the guard silently ignores entity-visibility. It lives outside the
  store on purpose (the store's lifecycle `find`/drafts/queue-flip must stay
  unfiltered), and the 2D-facade / 3D-direct read asymmetry blocks a clean single
  seam today. Fix: when **DEBT-2** lands a `Scene3DContext`, route both pipelines'
  display reads through one visibility-aware seam so no renderer can forget the
  filter. _Target: with DEBT-2._
