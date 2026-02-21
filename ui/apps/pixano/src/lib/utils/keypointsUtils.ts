/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { KeypointGraph } from "$lib/types/shapeTypes";

/**
 * Extract flat coord array and state array from keypoint vertices.
 * Coords are pushed as [x, y, x, y, ...]. States default to "visible".
 */
export function verticesToCoordsAndStates(
  vertices: ReadonlyArray<{ x: number; y: number; features: { state?: string } }>,
): { coords: number[]; states: string[] } {
  const coords: number[] = [];
  const states: string[] = [];
  for (const vertex of vertices) {
    coords.push(vertex.x);
    coords.push(vertex.y);
    states.push(vertex.features.state ? vertex.features.state : "visible");
  }
  return { coords, states };
}

export const findRectBoundaries = (vertices: KeypointGraph["vertices"]) => {
  const x = Math.min(...vertices.map((point) => point.x));
  const y = Math.min(...vertices.map((point) => point.y));
  const width = Math.max(...vertices.map((point) => point.x)) - x;
  const height = Math.max(...vertices.map((point) => point.y)) - y;
  return { x, y, width, height };
};
