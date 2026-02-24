/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { BoundingBox, Point2D } from "$lib/types/geometry";

/**
 * Pure geometry helpers for rectangle/bbox calculations and canvas view transforms.
 * No Konva stage lookups — all data is passed as parameters.
 */

// --- Rectangle / BBox helpers ---

/**
 * Normalize a rect after transform: collapse scale into width/height.
 */
export function normalizeRectAfterTransform(attrs: {
  x: number;
  y: number;
  width: number;
  height: number;
  scaleX: number;
  scaleY: number;
}): BoundingBox {
  return {
    x: attrs.x,
    y: attrs.y,
    width: attrs.width * attrs.scaleX,
    height: attrs.height * attrs.scaleY,
  };
}

/**
 * Compute normalised [x, y, w, h] coords relative to image dimensions.
 */
export function getRectNormalizedCoords(
  rectX: number,
  rectY: number,
  rectWidth: number,
  rectHeight: number,
  imageWidth: number,
  imageHeight: number,
): [number, number, number, number] {
  return [
    rectX / imageWidth,
    rectY / imageHeight,
    rectWidth / imageWidth,
    rectHeight / imageHeight,
  ];
}

/**
 * Clamp a dragged rectangle to stay within image boundaries.
 */
export function clampRectToImage(
  rectX: number,
  rectY: number,
  rectWidth: number,
  rectHeight: number,
  imageWidth: number,
  imageHeight: number,
): Point2D {
  return {
    x: Math.max(0, Math.min(rectX, imageWidth - rectWidth)),
    y: Math.max(0, Math.min(rectY, imageHeight - rectHeight)),
  };
}

// --- View transform helpers ---

export interface ViewTransform {
  readonly x: number;
  readonly y: number;
  readonly scaleX: number;
  readonly scaleY: number;
}

/**
 * Compute the initial view transform to fit an image in a grid cell.
 */
export function computeViewTransform(
  containerWidth: number,
  containerHeight: number,
  imageWidth: number,
  imageHeight: number,
  gridCols: number,
  gridRows: number,
  gridIndex: number,
): ViewTransform {
  const cellWidth = containerWidth / gridCols;
  const cellHeight = containerHeight / gridRows;

  const scaleByWidth = cellWidth / imageWidth;
  const scaleByHeight = cellHeight / imageHeight;
  const scale = Math.min(scaleByWidth, scaleByHeight);

  const gridX = gridIndex % gridCols;
  const gridY = Math.floor(gridIndex / gridCols);

  const offsetX = (cellWidth - imageWidth * scale) / 2 + gridX * cellWidth;
  const offsetY = (cellHeight - imageHeight * scale) / 2 + gridY * cellHeight;

  return { x: offsetX, y: offsetY, scaleX: scale, scaleY: scale };
}

/**
 * Compute a new view transform after a wheel-zoom event.
 */
export function zoomViewTransform(
  current: ViewTransform,
  direction: number,
  pointerX: number,
  pointerY: number,
  zoomSpeed: number = 1.05,
): ViewTransform {
  const oldScale = current.scaleX;

  const mousePointTo = {
    x: (pointerX - current.x) / oldScale,
    y: (pointerY - current.y) / oldScale,
  };

  const newScale = direction > 0 ? oldScale * zoomSpeed : oldScale / zoomSpeed;

  return {
    x: pointerX - mousePointTo.x * newScale,
    y: pointerY - mousePointTo.y * newScale,
    scaleX: newScale,
    scaleY: newScale,
  };
}
