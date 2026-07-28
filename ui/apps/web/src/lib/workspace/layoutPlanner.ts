/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { WidgetLayout } from "$lib/extensions/types.js";
import type { SchemaDescriptor } from "$lib/types/dataset";

/**
 * Pure layout planner for the record-selection grid, plus a thin
 * isolated DOM-measurement helper. The math functions take a `Viewport`
 * value so they're testable without a DOM; `measureGridViewport` is the
 * one and only place that reads `.grid-stack` from the live document.
 */

/**
 * GridStack column count and minimum cell size enforced by widget extensions
 * (image / point-cloud need w,h ≥ 3). These must stay in sync with the
 * GridWorkspace component's `column` setting; treat them as a single
 * source of truth and import from here rather than re-asserting inline.
 */
export const GRID_TOTAL_COLS = 12;
export const GRID_MIN_CELL = 3;
export const GRID_MAX_COLS = Math.floor(GRID_TOTAL_COLS / GRID_MIN_CELL); // 4

export interface Viewport {
  width: number;
  height: number;
}

/**
 * Filter a dataset's `views` map down to those whose `base` matches the
 * caller's predicate, preserving the dataset's declared order. Kept
 * predicate-driven so it doesn't bake in the set of supported bases.
 */
export function pickRenderableViews(
  views: Record<string, SchemaDescriptor> | undefined,
  isSupportedBase: (base: string) => boolean,
): Array<[string, SchemaDescriptor]> {
  if (!views) return [];
  return Object.entries(views).filter(([, def]) => !!def.base && isSupportedBase(def.base));
}

/**
 * Compute one `WidgetLayout` per visible widget so the whole set fits the
 * viewport on screen.
 *
 * GridStack uses 12 columns with `cellHeight: "auto"` (square cells), so
 * the number of visible rows ≈ `floor(containerH / (containerW / 12))`.
 *
 * Cell width and height are clamped to `GRID_MIN_CELL` because widget
 * extensions enforce that minimum; if we hand GridStack a smaller cell it
 * silently inflates the widget and breaks the alignment of the grid. We
 * also restrict cols to divisors of 12 (≤ `GRID_MAX_COLS`) so each row
 * fills the full width.
 */
export function planViewportLayouts(count: number, viewport: Viewport): WidgetLayout[] {
  if (count <= 0) return [];

  const containerW = Math.max(1, viewport.width);
  const containerH = Math.max(1, viewport.height);
  const visibleRows = Math.max(
    GRID_MIN_CELL,
    Math.floor((GRID_TOTAL_COLS * containerH) / containerW),
  );

  const cols = Math.max(1, Math.min(GRID_MAX_COLS, Math.ceil(Math.sqrt(count))));
  const rows = Math.ceil(count / cols);
  const w = Math.max(GRID_MIN_CELL, Math.floor(GRID_TOTAL_COLS / cols));
  const h = Math.max(GRID_MIN_CELL, Math.floor(visibleRows / rows));

  const layouts: WidgetLayout[] = [];
  for (let i = 0; i < count; i++) {
    const col = i % cols;
    const row = Math.floor(i / cols);
    layouts.push({ x: col * w, y: row * h, w, h });
  }
  return layouts;
}

/**
 * Default viewport for the workspace grid, measured from the live DOM.
 * This is the *only* place that reaches into `.grid-stack`; everything
 * downstream consumes the resulting numbers as plain data, so layout
 * decisions are testable without a DOM.
 *
 * Height is read from the grid's *parent* (the fixed, overflow-hidden
 * viewport wrapper) rather than from `.grid-stack` itself: GridStack
 * overrides the grid element's inline height to its content height
 * (`rows × cellHeight`), so measuring the grid would feed the current
 * widget sizes back into the next record's layout — enlarging a widget
 * would then ratchet every subsequent record larger until it runs
 * off-screen. The parent's height is stable and reflects the real
 * on-screen area. Width is unaffected (GridStack never rewrites it).
 *
 * Falls back to a reasonable 16:9 default when called from a non-browser
 * context (SSR) or before the grid has mounted.
 */
export function measureGridViewport(): Viewport {
  if (typeof document === "undefined") return { width: 1600, height: 900 };
  const el = document.querySelector<HTMLElement>(".grid-stack");
  const heightSource = el?.parentElement ?? el;
  return {
    width: el?.clientWidth ?? 1600,
    height: heightSource?.clientHeight ?? 900,
  };
}
