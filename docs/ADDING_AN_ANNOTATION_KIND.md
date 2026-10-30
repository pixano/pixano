# Adding a new annotation kind / tool — `ui/apps/web`

Adding an annotation kind is a **plugin** operation: one new folder under
`lib/annotations/kinds/` plus one line in each registry. If a step makes you edit a
widget, the scene, or the mutation queue, **stop — you are doing it wrong**; fix the
seam instead. See `ARCHITECTURE_TOOLING.md` for the rationale and `CODING_STANDARDS.md`
for the rules.

## Invariants (do not break these)

- **Store / display / edit are separate files.** Payload builder + seed loader = store;
  a renderer = display; a tool/editor = input. Never mix them in one class.
- **The widget and the scene name no kind.** They iterate registries; your kind is
  discovered, never hard-wired.
- **Renderers cannot write.** A 2D renderer receives a read-only `Scene2DReadContext`
  (no `mutations`, no `setActiveTool`). Editing input lives in a tool/editor that gets
  the full context.
- **Never hand-build mutations.** Use `commitNewAnnotation` / `commitGeometryEdit`
  (`payloadBuilders.ts`) — they own the draft→queue→persist lifecycle for every kind.
- **Work a tool holds is the record's unsaved work.** A shape begun and not committed —
  points before Enter, a box being drawn — is in no mutation. Its holder claims a
  staged-work flag of its own, once (`ctx.claimStagedWork(discard)`), raises it while it
  holds the work and lowers it on every way out; `discard` drops the work, and the record's
  Discard calls it. Each raised flag counts as one item of the record's unsaved count.
  Without the flag, the count reads 0 over the work, and Discard leaves it in place.
  - A box being resized is such work too, held by its editor.
  - So is a shape being dragged, held by its editor.
- **Keys typed in a form field belong to it.** A key listener on `window` — a tool's
  shortcut, an editor's Escape — returns early when `isFormFieldTarget(event.target)`
  (`scene/tool.ts`): a select picks an option with the keys typed in it, and an `E` or a
  Backspace there must not reassign or delete the selection, nor Escape drop a 3D edit.
- **No shared magic strings between files.** If two files agree on a literal (e.g. a
  Konva node `name`), put it in one `<kind>...Nodes.ts` / `Constants.ts` and import it
  (see `bbox2dNodes.ts`).
- **SOLID / standards:** strict TS (no `any`; precise tuples, not `number[]`), no magic
  numbers, license header on every file, tests for all logic.

## Step 0 — decide the shape

1. **Which medium?** 2D image (Konva) or 3D point cloud (Threlte). They share the data
   layer but have different display/input mechanics (D3 — no universal tool interface).
2. **Display-only, or editable?** Editable kinds add an input handler on top of the renderer.
3. **(3D only) does creation need a confirm step?** If yes, add a session + HUD (like bbox3d).

## Step 1 — declare the kind (shared)

In `lib/annotations/annotationCollection.svelte.ts`:
- add the literal to the `AnnotationKind` union;
- add its geometry type to `GeometryByKind` (precise types).

Create `lib/annotations/kinds/<2d|3d>/<kind>/` and, in it, `<kind>Types.ts` — the geometry
type + any kind-specific types (mirror `bbox3dTypes.ts`).

## Step 2 — the STORE half (both media)

- `<kind>PayloadBuilder.ts` — implement `PayloadBuilder` (`buildCreate`, `buildUpdate`);
  the only place that knows the backend `resource` name and body shape.
  **Invariant (D9):** `buildUpdate`'s body must be a superset of `buildCreate`'s geometry
  fields with identical values otherwise, so `commitGeometryEdit` can patch a pending
  create with it.
  **`buildUpdate` follows from the annotation alone.** A field taken from anywhere else
  rewrites, on every edit, a part of the row the person did not change. A
  record-scoped kind writes the row's own view and stored format, never the editing
  widget's (`bbox3dPayloadBuilder.buildUpdate`).
  → register in `PAYLOAD_BUILDERS` (`payloadBuilders.ts`).
- `<kind>SeedLoader.ts` — REST rows → `LocalAnnotation[]`, once per record.
  For a view-scoped kind, do **not** hand-roll the fetch/filter/wrap loop: call
  `createViewScopedSeedLoader({ kind, resource, toGeometry })`
  (`viewScopedSeedLoader.ts`) and supply only `toGeometry(row, view)`, returning
  `null` to drop a malformed row. The fetch, the view filter and the
  `LocalAnnotation` envelope are shared so they cannot drift per kind.
  A record-scoped kind (`bbox3d`) implements `AnnotationSeedLoader` directly,
  since it deliberately keeps rows whose view is not displayed.
  **A failed fetch rejects**, in either case: never catch it into an empty list. An
  empty list reads as a table holding nothing, and a reload would take every
  annotation of the kind off the screen after one failed request. What a failure means
  is the caller's to decide (`loadEveryKind`, `seedLoaders.ts`): a record opening seeds
  nothing for the kind, a reload keeps what the kind shows. `seedLoaders.test.ts`
  fails every registered loader in turn, so a loader that swallows its failure fails it.
  → register in `SEED_LOADERS` (`seedLoaders.ts`).

## Step 3 — the DISPLAY + INPUT halves

### 2D (Konva)

- `<kind>Renderer2D.ts` — implement `AnnotationRenderer2D` (`kind`, `sync()`, `destroy()`).
  Takes a `Scene2DReadContext`. Draws nodes, does click→`collection.select`, follows labels
  on drag. **Must not** commit or own a transformer. Stamp a shared node `name`/id-attr
  from a `<kind>Nodes.ts` module.
- `<kind>Editor2D.ts` (editable only) — implement `AnnotationEditor2D` (`kind`,
  `syncSelection()`, `destroy()`). Takes the full `Scene2DContext`. Owns the interaction
  widget (e.g. `Konva.Transformer`), listens for each gesture's end **where Konva fires
  it**, and commits via `commitGeometryEdit`: a drag's end (`dragend`) bubbles, so the
  layer hears it for every node the editor did not create; a resize's end
  (`transformend`) fires on the transformer and the nodes it holds only, never on the
  layer, so listen on the editor's own transformer (`bboxEditor2D.ts`). A renderer that
  sets a node's size resets its scale and rotation, which a resize leaves behind. A
  transformer whose shape cannot hold a flip is built with `flipEnabled: false`: Konva
  records a handle dragged past the opposite edge as a negative scale or a half turn, and
  the shape saved then differs from the shape drawn. Expose it from the renderer factory's
  `createEditor`.

  Commit geometry the server accepts: the box editor keeps a dragged box whole inside the
  image and cuts a resized one at its edges, putting on the image's edge a box edge within
  `IMAGE_EDGE_TOLERANCE` of it (`bboxImageBounds.ts`), since the server refuses a
  normalized coordinate outside [0, 1]. The cut keeps the least size the editor gives a box
  (`MIN_BBOX_PIXELS`): a box resized wholly past the edge it lies on keeps that size
  against the edge rather than being saved with no width, which no handle could resize
  again. And a node Konva left with no number for its place or size — a box stored with no
  width, which it cannot scale — commits nothing: the box is drawn again as stored.

  A resize is work of its own until it ends — the new size sits on the node — so the editor
  holds a staged-work flag while it runs, keeps hold of its nodes whatever the selection
  does, and marks them (`BBOX_RESIZING_ATTR` in `bbox2dNodes.ts`) so the renderer's sync —
  a save ending — leaves their size and place alone; its discard stops the resize and
  redraws the box as stored.

  A drag is held the same way, whatever the shape: the editor listens for `dragstart` as
  well as `dragend` on the layer, raises its flag at the start and lowers it at the end —
  once per drag, never per pointer move — and stamps the dragged node, or the group of the
  shape whose point is dragged, with a `<KIND>_DRAGGING_ATTR` from the kind's own
  `<kind>Types.ts` / `<kind>Nodes.ts` (`BBOX_DRAGGING_ATTR`, `MASK_DRAGGING_ATTR`,
  `MULTI_PATH_DRAGGING_ATTR`, `KEYPOINTS_DRAGGING_ATTR`). The renderer's sync leaves a
  stamped node alone: it neither moves it back nor rebuilds it. The editor commits only a
  drag whose start it saw, and unstamps the node first, so the commit's redraw draws the
  shape where it was let go; its discard lets go of the drag, stops it (`stopDrag`: the
  `dragend` that follows finds nothing held and commits nothing) and redraws the shape as
  stored (`bboxEditor2D.ts`, `maskEditor2D.ts`). A kind whose geometry is a flat list of
  points edits through the shared `scene/flatCoordsEditor2D.ts`, which holds the drag
  itself — the flag, the stamp on the shape's group, the commit of a drag it saw begin, the
  discard — so the kind writes no editor: its factory's `createEditor` returns
  `createFlatCoordsEditor2D(ctx, spec)`, the spec naming the kind's node labels and its
  dragging attribute (`draggingAttr: MULTI_PATH_DRAGGING_ATTR`, declared in its own
  `<kind>Types.ts`), and its renderer leaves a group so stamped alone
  (`multiPathRenderer2D.ts`, `keypointsRenderer2D.ts`).
- `draw<Kind>Tool.ts` — a `Tool2D` (`createHandler(ctx): ToolHandler2D`) for the creation
  gesture; on finish, `commitNewAnnotation(ctx, "<kind>", geometry)` then hand back to `select`.
  A handler that holds work not in the collection yet — points placed, strokes painted, a
  box being drawn — claims a staged-work flag in its constructor
  (`ctx.claimStagedWork?.(() => this._reset())`), raises it as that work begins, and lowers
  it on commit, Escape, `deactivate`, and an undo that removes the last point. Its discard
  callback is its reset. The contract is written on `ToolHandler2D` (`scene/tool.ts`);
  `drawMultiPathTool.ts` is the example.

→ register the factory in `RENDERER_FACTORIES_2D` and the tool in `TOOLS_2D` (`registry2d.ts`).

### 3D (Threlte)

- `<Kind>Renderer.svelte` — the display component; reads `ctx.collection.byKind("<kind>")`
  and emits `<T.*>` nodes. Skip `ctx.editingId` (the tool draws that one live). Reuse
  geometry (shared, scaled) — never allocate per item in the reactive derivation.
  → register `{ kind, component }` in `RENDERER_FACTORIES_3D` (`registry3d.ts`).
- `<Kind>Tool.svelte` — the `Tool3D.overlay`: constructs the editor (its `$effect`s need a
  component scope), renders the transient preview/gizmos, and reports a `ToolHandle3D`
  (`activeDragging`, `editingId`) via `reportHandle`.
- `<kind>Session.svelte.ts` (if it needs a confirm step) — a class holding the transient
  confirm state + tool-UI state, with `save()`/`cancel()` that call the commit helpers. It
  lives in the kind so the widget stays kind-agnostic.
- `<Kind>Hud.svelte` — the `Tool3D.hud`: the DOM confirm/secondary UI, driven by the session.
- `draw<Kind>Tool.ts` — the `Tool3D` entry wiring `overlay` + `createSession` + `hud`.

→ register in `TOOLS_3D` (`registry3d.ts`).

## Step 4 — tests (required)

- Payload builder unit tests (bodies, ids, flags).
- The write path is covered generically by `commit.test.ts`; add kind-specific tests for
  your editor/session logic — assert a gesture/confirm commits the right geometry.
  - Run a 2D editor on the real Konva over the real workspace, as `bboxEditor2D.test.ts`
    does (`scene/__tests__/konvaInHappyDom.ts` gives happy-dom a canvas; `openManager` and
    `widgetSeam` come from `workspace/__tests__/workspaceHarness.ts`): a mocked Konva
    answers whatever the mock says, and can pass while a resize goes unsaved.
  - An editable 2D kind drags a shape across a save there (`multiPathDrag.test.ts`): the
    flag is raised once for the drag, the save leaves the shape where it is dragged, the
    release saves it, and Discard drops the drag. Send a window `mouseup` after each test:
    Konva's drags are global, and one a failed test left running moves with the next
    test's pointer.
- A tool-lifecycle test where practical (see `drawBBoxTool.test.ts`, `selectTool2D.test.ts`).
  A tool that holds work runs once in an image widget of a record open in the real
  workspace (`openManager` and `widgetSeam`), as `drawMultiPathTool.test.ts` does: the
  record holds unsaved work while the work is held, the flag goes down on commit, Escape
  and deactivate, and Discard leaves nothing to commit.

## Step 5 — verify

- `pnpm run check` adds **no** new errors; `pnpm exec vitest run` green;
  `pnpm run build` green (catches the `.svelte`-into-registry imports).
- Grep the widget/scene: your kind name must appear **nowhere** in `PointCloudWidget`,
  `PointCloudScene`, or `ImageWidget`.

## Checklist

- [ ] `AnnotationKind` + `GeometryByKind` updated
- [ ] `kinds/<2d|3d>/<kind>/` created; `<kind>Types.ts`
- [ ] payload builder + `PAYLOAD_BUILDERS`; `buildUpdate` follows from the annotation alone
- [ ] seed loader + `SEED_LOADERS`, rejecting on a failed fetch
- [ ] renderer + `RENDERER_FACTORIES_2D|3D`
- [ ] editor (2D `createEditor`) / overlay+session+hud (3D) if editable
- [ ] every holder of unconfirmed work (2D tool handler, editor gesture) claims a staged-work flag, lowers it on every way out, and drops its work on discard; window key listeners ask `isFormFieldTarget`
- [ ] tool + `TOOLS_2D|3D`
- [ ] write path uses `commitNewAnnotation` / `commitGeometryEdit` only
- [ ] shared literals extracted (no cross-file magic strings)
- [ ] tests added; `check` / `vitest` / `build` green; no widget/scene edits

## Adding a whole new *medium* (e.g. text), not just a kind

> Note: the existing `TextWidget.svelte` is a display-only Tiptap host — it has no
> seam, renderer or tool, so it is not an example of this. Text *annotation* is
> still unbuilt.

That is a bigger job: build the widget with `buildSeam(manager, …)`, define a
`Scene<Medium>Context extends SceneContextBase` with the medium's engine handle, and add
renderer/tool interfaces mirroring the 2D/3D ones. Everything below the seam
(`AnnotationCollection`, `MutationQueue`, seed loaders, payload builders, commit helpers,
`buildSeam`, `<AnnotationToolbar>`) is reused unchanged. See `ARCHITECTURE_TOOLING.md`
"Adding a new medium".
