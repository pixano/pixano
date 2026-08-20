/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";

import type { CoordsNorm } from "$lib/annotations/types.js";

export const PIXEL_THRESHOLD = 3;
export const BBOX_COLOR_PERSISTED = "#22d3ee";
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
 * are live. Shared so the three read as one visual language.
 */
export const SELECTED_STROKE_SCALE = 2;

/** Extra opacity a filled or raster annotation gains while selected. */
export const SELECTED_OPACITY_BOOST = 0.2;

export interface PixelFrame {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** A point in Konva stage space. */
export interface PixelPoint {
  x: number;
  y: number;
}

export function getPixelFrame(konvaImage: Konva.Image | null): PixelFrame | null {
  if (!konvaImage) return null;
  return { x: konvaImage.x(), y: konvaImage.y(), w: konvaImage.width(), h: konvaImage.height() };
}

export function normalizedToPixel(
  coords: CoordsNorm,
  frame: PixelFrame,
): { x: number; y: number; width: number; height: number } {
  return {
    x: frame.x + coords[0] * frame.w,
    y: frame.y + coords[1] * frame.h,
    width: coords[2] * frame.w,
    height: coords[3] * frame.h,
  };
}

/**
 * Map a normalized point onto the frame, writing the result into `target`
 * (Three.js `getWorldPosition(target)` convention) rather than returning a
 * fresh object: the bbox3d projection calls this once per corner, per box, per
 * sync — and sync runs on every pointer move while a 3D box is dragged, so the
 * path must not allocate (CODING_STANDARDS). Returns `target` for chaining.
 */
export function normalizedPointToPixel(
  x: number,
  y: number,
  frame: PixelFrame,
  target: PixelPoint,
): PixelPoint {
  target.x = frame.x + x * frame.w;
  target.y = frame.y + y * frame.h;
  return target;
}

/**
 * Stage pixels → normalized [0,1], the inverse of `normalizedPointToPixel`.
 *
 * Kinds whose geometry is a flat list of points (keypoints skeletons,
 * multi-path rings) need this to turn a dragged handle back into stored
 * coordinates. Clamped, because a handle can be dragged past the media edge and
 * the backend validators reject a coordinate outside [0,1] — dropping the whole
 * edit over a few pixels of overshoot would be worse than pinning it to the
 * border.
 */
export function pixelPointToNormalized(x: number, y: number, frame: PixelFrame): PixelPoint {
  return {
    x: clampUnit((x - frame.x) / frame.w),
    y: clampUnit((y - frame.y) / frame.h),
  };
}

function clampUnit(value: number): number {
  return Math.min(1, Math.max(0, value));
}

export function pixelToNormalized(
  rectX: number,
  rectY: number,
  rectW: number,
  rectH: number,
  frame: PixelFrame,
): CoordsNorm {
  return [
    (rectX - frame.x) / frame.w,
    (rectY - frame.y) / frame.h,
    rectW / frame.w,
    rectH / frame.h,
  ];
}
