/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";

import type { CoordsNorm } from "$lib/annotations/types.js";

export const PIXEL_THRESHOLD = 3;
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

/**
 * Pin a normalized coordinate inside [0, 1].
 *
 * Shared because every editor needs it for the same reason: a handle can be
 * dragged past the media edge, and the backend validators reject a coordinate
 * outside the unit square — losing a whole edit over a few pixels of overshoot
 * would be worse than pinning it to the border.
 */
export function clampUnit(value: number): number {
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
