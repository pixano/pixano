/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** Pure, immutable helper functions for canvas view transforms. */

export interface ViewTransform {
  readonly x: number;
  readonly y: number;
  readonly scaleX: number;
  readonly scaleY: number;
}

/**
 * Compute the initial view transform to fit an image in a grid cell.
 *
 * @param containerWidth  Total container width (px)
 * @param containerHeight Total container height (px)
 * @param imageWidth      Source image width
 * @param imageHeight     Source image height
 * @param gridCols        Number of columns in the multi-view grid
 * @param gridRows        Number of rows in the multi-view grid
 * @param gridIndex       0-based position in the grid (left-to-right, top-to-bottom)
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
 *
 * @param current     Current transform
 * @param direction   Positive to zoom in, negative to zoom out
 * @param pointerX    Pointer X relative to the stage
 * @param pointerY    Pointer Y relative to the stage
 * @param zoomSpeed   Multiplicative zoom factor per step (default 1.05)
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
