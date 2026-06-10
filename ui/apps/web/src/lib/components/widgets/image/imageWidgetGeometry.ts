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

export interface PixelFrame {
  x: number;
  y: number;
  w: number;
  h: number;
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
