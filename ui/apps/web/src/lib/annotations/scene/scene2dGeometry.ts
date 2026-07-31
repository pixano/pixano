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
