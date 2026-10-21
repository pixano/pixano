/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { clampUnit } from "$lib/annotations/scene/scene2dGeometry.js";
import type { CoordsNorm } from "$lib/annotations/types.js";

/**
 * How close to an edge of the image a box's edge may land and still be on it,
 * in normalized units. A box let go on the edge comes back from pixels a
 * float's error away from it — -8.9e-18, a hair past the left edge, which the
 * server refuses — while a pixel of an image even 100 000 px wide is 1e-5.
 * Anything this close is the edge itself.
 */
export const IMAGE_EDGE_TOLERANCE = 1e-9;

/** A box edge put on the image's edge it lands within `IMAGE_EDGE_TOLERANCE` of, if any. */
function onImageEdge(value: number): number {
  if (Math.abs(value) <= IMAGE_EDGE_TOLERANCE) return 0;
  if (Math.abs(1 - value) <= IMAGE_EDGE_TOLERANCE) return 1;
  return value;
}

/**
 * A dragged box kept inside the image, whole: dropped past an edge, it stops
 * against it — the person moved the box, and did not mean to shrink it.
 *
 * @param coords The box where the drag let go of it, normalized `[x, y, w, h]`.
 * @returns The box inside the image: `x, y ≥ 0`, `x + w ≤ 1`, `y + h ≤ 1`.
 */
export function movedInsideImage([x, y, w, h]: CoordsNorm): CoordsNorm {
  const width = clampUnit(w);
  const height = clampUnit(h);
  return [
    onImageEdge(Math.min(1 - width, Math.max(0, x))),
    onImageEdge(Math.min(1 - height, Math.max(0, y))),
    width,
    height,
  ];
}

/** The least size a box keeps, normalized: a fraction of the image's width and of its height. */
export interface MinimumBoxSize {
  readonly width: number;
  readonly height: number;
}

/**
 * A resized box cut at the image's edges: a handle taken past one puts the
 * box's edge on it, since what lies beyond is not the image's.
 *
 * The cut never leaves less than the least size. A box resized wholly beyond
 * an edge of the image would be cut to nothing: a box of no width, which the
 * server stores and no handle can resize again. It keeps the least size
 * instead, against that edge: its free edge is put back inside the image.
 *
 * @param coords The box as the resize left it, normalized `[x, y, w, h]`.
 * @param minimum The least width and height the box keeps, normalized.
 * @returns The part of the box on the image: `x, y ≥ 0`, `x + w ≤ 1`, `y + h ≤ 1`,
 *   `w` and `h` no less than `minimum`.
 */
export function cutAtImageEdges([x, y, w, h]: CoordsNorm, minimum: MinimumBoxSize): CoordsNorm {
  const [left, right] = cutSpan(x, x + w, minimum.width);
  const [top, bottom] = cutSpan(y, y + h, minimum.height);
  return [left, top, right - left, bottom - top];
}

/**
 * One axis of `cutAtImageEdges`: the span from `start` to `end`, cut at the
 * image's edges, then given back the least length if the cut left it less —
 * from the edge it starts at, unless that would take it past the image's far
 * edge, where it then lies.
 */
function cutSpan(start: number, end: number, minimum: number): [number, number] {
  const low = onImageEdge(clampUnit(start));
  const high = onImageEdge(clampUnit(end));
  if (high - low >= minimum) return [low, high];
  // An image narrower than the least size holds a box as wide as itself.
  const length = Math.min(1, minimum);
  return low + length <= 1 ? [low, low + length] : [1 - length, 1];
}
