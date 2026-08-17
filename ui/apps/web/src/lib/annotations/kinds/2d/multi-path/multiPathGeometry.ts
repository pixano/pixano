/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { MultiPathGeometry } from "./multiPathTypes.js";
import type { PixelFrame } from "$lib/annotations/scene/scene2dGeometry.js";

/**
 * Slicing the flat `coords` list into sub-paths is the one operation the
 * renderer and the tool both need, and getting the offsets wrong draws a shape
 * that exists nowhere in the data — so it lives here once rather than twice.
 */

/** A sub-path's points, already mapped to stage pixels for Konva. */
export type PixelSubPath = number[];

/**
 * Split a geometry into per-sub-path point lists, in Konva's flat
 * `[x0, y0, x1, y1, …]` form and in stage pixels.
 *
 * Trailing coordinates that `numPoints` does not account for are dropped rather
 * than guessed at: the seed loader rejects such rows, so reaching this with a
 * mismatch means a tool built one, and drawing it would hide the bug.
 */
export function toPixelSubPaths(geometry: MultiPathGeometry, frame: PixelFrame): PixelSubPath[] {
  const subPaths: PixelSubPath[] = [];
  let offset = 0;
  for (const count of geometry.numPoints) {
    if ((offset + count) * 2 > geometry.coords.length) break;
    const flat: number[] = [];
    for (let i = 0; i < count; i++) {
      const x = geometry.coords[(offset + i) * 2];
      const y = geometry.coords[(offset + i) * 2 + 1];
      flat.push(frame.x + x * frame.w, frame.y + y * frame.h);
    }
    subPaths.push(flat);
    offset += count;
  }
  return subPaths;
}

/** Assemble a geometry from sub-paths held as normalized point lists. */
export function fromNormalizedSubPaths(
  subPaths: readonly (readonly { x: number; y: number }[])[],
  isClosed: boolean,
): MultiPathGeometry {
  const coords: number[] = [];
  const numPoints: number[] = [];
  for (const points of subPaths) {
    if (points.length === 0) continue;
    for (const point of points) coords.push(point.x, point.y);
    numPoints.push(points.length);
  }
  return { coords, numPoints, isClosed };
}
