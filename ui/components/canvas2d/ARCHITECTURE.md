# Canvas2D Architecture Audit & Refactor Status

## Audit Summary

`Canvas2D.svelte` currently mixes too many concerns:

- Rendering (Konva scene graph)
- Tool policy (which tools are allowed and defaults)
- Tool orchestration (tool switching, keyboard shortcuts)
- Tool-FSM bridge wiring (`@pixano/tools` + `@pixano/store`)
- Shape creation flows (rectangle, brush, polygon, keypoint)
- Smart-mask/inference-specific behavior
- Image processing/filter pipelines

This creates tight coupling and makes the file difficult to reason about.

## Scope Enforced (Current)

The Canvas2D runtime now enforces a reduced migration scope:

- Supported tools: `Pan`, `Rectangle`, `Brush`
- Unsupported/legacy interaction paths removed from `Canvas2D.svelte`:
  - Smart mask inference flow
  - Point-selection interaction flow
  - Polygon creation flow
  - Keypoint creation flow
- Existing annotations are still rendered, but only the active migration toolset is interactive.

This removed a large amount of branching in event/key handlers and reduced `Canvas2D.svelte` size from ~1900 LOC to ~1300 LOC.

## Refactor Foundation Added

To make behavior explicit and composable, two dedicated tooling modules were added:

- `src/tooling/toolPolicy.ts`
  - Supported tool policy (`Pan`, `Rectangle`, `Brush`)
  - Keyboard shortcut policy (Esc/R/B/X/Q/E/Save)
  - Canonical fallback tool and brush mode toggling

- `src/tooling/bridgeRuntime.ts`
  - Internal `ToolBridge` bootstrap
  - Explicit mapping from workspace `SelectionTool` to FSMs:
    - `PanToolFSM`
    - `RectangleToolFSM`
    - `BrushToolFSM`

`Canvas2D.svelte` now delegates policy and FSM selection to these modules instead of embedding those rules inline.

## Long-Term Target Structure

Recommended next extraction units:

1. `runtime/interactionRuntime.ts`
   - Stage mouse/keyboard dispatch and pointer lifecycle
2. `runtime/rectangleRuntime.ts`
   - Rectangle preview + transformer sync + save adapter
3. `runtime/brushRuntime.ts`
   - Brush cursor, stroke lifecycle, mask save flow
4. `runtime/viewLayoutRuntime.ts`
   - Grid layout, zoom, resize, filter updates

Each runtime should expose pure(ish) functions with narrow dependencies, so the Svelte file becomes an orchestrator rather than a logic host.

## Policy for Ongoing Migration

- Keep `Canvas2D.svelte` as composition root only.
- Add new tool logic under `src/tooling`/`src/runtime` first, then call from Svelte.
- Do not add new direct `@pixano/*` domain logic in `Canvas2D.svelte`; place adapters in dedicated modules.
- Integrate all new tools via FSM + bridge mapping (`bridgeRuntime.ts`).
