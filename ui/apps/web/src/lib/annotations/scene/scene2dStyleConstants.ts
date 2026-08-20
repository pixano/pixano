/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";

/**
 * The visual language every 2D annotation kind draws itself in.
 *
 * Split from `scene2dGeometry.ts`, which is coordinate maths: these are the
 * appearance decisions, and they are shared rather than per-kind so a mask, a
 * ring and a skeleton cannot end up saying "selected" or "unsaved" three
 * different ways.
 */

/** Fill/stroke of an annotation already stored in the backend. */
export const BBOX_COLOR_PERSISTED = "#22d3ee";

/** Fill/stroke of one still waiting to be saved. */
export const BBOX_COLOR_DRAFT = "#f59e0b";

/**
 * Dash pattern marking a shape as not-yet-saved: the draw tool's rubber band,
 * an unsaved bbox, and the live 3D preview all share it so "dashed = draft"
 * reads the same everywhere. Frozen because Konva keeps the array by reference
 * — a mutation here would silently restyle every draft on screen.
 */
export const DRAFT_DASH: readonly number[] = Object.freeze([6, 4]);

/**
 * Radius of a vertex handle's *clickable* area, in stage pixels.
 *
 * Deliberately far larger than the dot drawn on screen. A handle is rendered
 * small so a dense skeleton or ring stays readable, but a small drawn dot makes
 * a small target: a click that misses one falls through to the stage, which
 * **deselects**, so the next drag silently does nothing and the tool looks
 * broken. Widening only the hit region keeps the display honest and the target
 * reachable.
 */
export const VERTEX_HIT_RADIUS = 12;

/**
 * How much heavier a shape's outline gets while it is the selected annotation.
 *
 * Every kind but bbox needs its own selected look: a bbox announces selection
 * with the editor's `Konva.Transformer`, but a ring, a skeleton or a raster get
 * no handles of that sort, so without this they look identical selected and
 * not — while selection is exactly what decides whether their vertex handles
 * are live.
 */
export const SELECTED_STROKE_SCALE = 2;

/** Extra opacity a filled or raster annotation gains while selected. */
export const SELECTED_OPACITY_BOOST = 0.2;

/**
 * Konva `hitFunc` giving a vertex handle its oversized grab area.
 *
 * A module-level function, not a closure built per handle: it captures nothing,
 * and `sync()` re-creates every node on each collection change, so building one
 * per vertex per sync would allocate for no reason.
 */
export function drawVertexHitArea(context: Konva.Context, shape: Konva.Shape): void {
  context.beginPath();
  context.arc(0, 0, VERTEX_HIT_RADIUS, 0, Math.PI * 2, false);
  context.closePath();
  context.fillStrokeShape(shape);
}
