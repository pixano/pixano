/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Pure geometry helpers for rectangle/bbox calculations.
 * No Konva stage lookups — all data is passed as parameters.
 */

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
}): { x: number; y: number; width: number; height: number } {
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
): { x: number; y: number } {
  return {
    x: Math.max(0, Math.min(rectX, imageWidth - rectWidth)),
    y: Math.max(0, Math.min(rectY, imageHeight - rectHeight)),
  };
}
