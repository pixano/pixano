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
  create with it. → register in `PAYLOAD_BUILDERS` (`payloadBuilders.ts`).
- `<kind>SeedLoader.ts` — implement `AnnotationSeedLoader` (REST rows → `LocalAnnotation[]`,
  once per record). → register in `SEED_LOADERS` (`seedLoaders.ts`).

## Step 3 — the DISPLAY + INPUT halves

### 2D (Konva)

- `<kind>Renderer2D.ts` — implement `AnnotationRenderer2D` (`kind`, `sync()`, `destroy()`).
  Takes a `Scene2DReadContext`. Draws nodes, does click→`collection.select`, follows labels
  on drag. **Must not** commit or own a transformer. Stamp a shared node `name`/id-attr
  from a `<kind>Nodes.ts` module.
- `<kind>Editor2D.ts` (editable only) — implement `AnnotationEditor2D` (`kind`,
  `syncSelection()`, `destroy()`). Takes the full `Scene2DContext`. Owns the interaction
  widget (e.g. `Konva.Transformer`), listens at the **layer** level for the gesture end,
  and commits via `commitGeometryEdit`. Expose it from the renderer factory's `createEditor`.
- `draw<Kind>Tool.ts` — a `Tool2D` (`createHandler(ctx): ToolHandler2D`) for the creation
  gesture; on finish, `commitNewAnnotation(ctx, "<kind>", geometry)` then hand back to `select`.

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
  your editor/session logic through a fake context (see `bboxEditor2D.test.ts`,
  `bbox3dSession.test.ts`) — assert a gesture/confirm commits the right geometry.
- A tool-lifecycle test where practical (see `drawBBoxTool.test.ts`, `selectTool2D.test.ts`).

## Step 5 — verify

- `pnpm run check` adds **no** new errors; `pnpm exec vitest run` green;
  `pnpm run build` green (catches the `.svelte`-into-registry imports).
- Grep the widget/scene: your kind name must appear **nowhere** in `PointCloudWidget`,
  `PointCloudScene`, or `ImageWidget`.

## Checklist

- [ ] `AnnotationKind` + `GeometryByKind` updated
- [ ] `kinds/<2d|3d>/<kind>/` created; `<kind>Types.ts`
- [ ] payload builder + `PAYLOAD_BUILDERS`
- [ ] seed loader + `SEED_LOADERS`
- [ ] renderer + `RENDERER_FACTORIES_2D|3D`
- [ ] editor (2D `createEditor`) / overlay+session+hud (3D) if editable
- [ ] tool + `TOOLS_2D|3D`
- [ ] write path uses `commitNewAnnotation` / `commitGeometryEdit` only
- [ ] shared literals extracted (no cross-file magic strings)
- [ ] tests added; `check` / `vitest` / `build` green; no widget/scene edits

## Adding a whole new *medium* (e.g. text), not just a kind

That is a bigger job: build the widget with `buildSeam(manager, …)`, define a
`Scene<Medium>Context extends SceneContextBase` with the medium's engine handle, and add
renderer/tool interfaces mirroring the 2D/3D ones. Everything below the seam
(`AnnotationCollection`, `MutationQueue`, seed loaders, payload builders, commit helpers,
`buildSeam`, `<AnnotationToolbar>`) is reused unchanged. See `ARCHITECTURE_TOOLING.md`
"Adding a new medium".
