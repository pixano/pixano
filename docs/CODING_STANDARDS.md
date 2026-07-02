# Coding Standards — `ui/apps/web`

> Companion to [ARCHITECTURE_TOOLING.md](./ARCHITECTURE_TOOLING.md). These standards apply to the
> next-UI workspace app and especially to annotation tooling code.

## Architecture rules

- **New annotation kinds are plugins.** A new kind lives entirely under
  `lib/annotations/kinds/<kind>/` (geometry type, payload builder, renderer,
  tools) plus registry registrations. If adding a kind requires editing a widget
  component, a mode union, or the mutation queue, the change is wrong — fix the
  seam instead.
- **Widgets are hosts, not tools.** Widget components own scene setup (Konva
  stage / Threlte canvas), layout, and delegation. They must not contain
  tool-specific branches (`if (mode === "draw-x")`) or annotation-kind logic.
- **One local model.** All in-widget annotation state uses
  `LocalAnnotation<G>` inside an `AnnotationCollection`. Do not introduce new
  per-kind draft/override structures.
- **2D and 3D tool interfaces stay separate** (`Tool2D` / `Tool3D`). Do not
  build a universal scene abstraction; share only `ToolDefinition` metadata.
- **Renderers ≠ tools.** Code that displays persisted annotations goes in a
  renderer; code that handles user input goes in a tool handler.
- **Depend on interfaces at boundaries.** Tools and renderers receive a
  `Scene2DContext` / `Scene3DContext`; queue code depends on `MutationGateway`
  and `LocalAnnotationLocator` only. Never reach for the concrete
  `WorkspaceManager` from inside a tool or renderer.

## Svelte / TypeScript

- Svelte 5 runes only (`$state`, `$derived`, `$effect`); no legacy stores in new
  code. Stateful domain classes live in `.svelte.ts` files (existing pattern:
  `AnnotationCollection`, tool handlers).
- Strict TypeScript: no implicit `any`, no `var`, prefer `const` and
  immutability. Geometry types are precise tuples (e.g.
  `[number, number, number, number]`), not `number[]`.
- UI text goes through translation keys (`labelKey` on `ToolDefinition`), never
  string literals in components.
- No magic numbers: named constants in a `*Constants.ts` module next to their
  consumer (existing pattern: `boxEditorConstants.ts`).
- Pre-allocate Three.js scratch objects (vectors, quaternions, meshes) as class
  fields; never allocate in pointer-event or render-loop code paths.
- License header required on every `.ts` / `.svelte` file (pre-commit enforced).

## Testing

- Every payload builder, geometry transform, and `AnnotationCollection`
  behaviour has unit tests (vitest). Tool handlers are tested through their
  context interface with a fake scene context.
- A new annotation kind ships with: builder tests, renderer sync tests, and at
  least one tool-lifecycle test (activate → draw → commit → queue contents).
- `pnpm run check` (svelte-check) must not add errors; run `vitest run` before
  every commit.

## Process

- Branch from `frontend/next-ui-init`; conventional commit messages; atomic
  commits; self-review before each commit.
- Refactoring phases (see ARCHITECTURE_TOOLING.md migration plan) land as separate PRs;
  never mix a phase with feature work.
