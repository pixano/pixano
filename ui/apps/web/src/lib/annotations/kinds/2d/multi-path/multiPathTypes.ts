/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Geometry of a multi-path, held as the backend stores it.
 *
 * One kind covers both polygons and polylines, exactly as the backend's
 * `MultiPath` does: the layout is GeoJSON-shaped, with every sub-path's points
 * concatenated into one flat `coords` list and `numPoints` recording how many
 * belong to each. `isClosed` is what separates the two readings —
 * a multi-polygon (closed rings) from a multi-linestring (open paths).
 *
 * Invariants the backend enforces and the seed loader re-checks:
 * `coords.length` even, `sum(numPoints) * 2 === coords.length`, every
 * coordinate in [0,1], and at least 3 points per sub-path when closed (2 when
 * open) — below that a ring or a segment does not exist.
 */
export interface MultiPathGeometry {
  /** Flat, normalized `[x0, y0, x1, y1, …]` across all sub-paths. */
  coords: number[];
  /** Point count per sub-path, e.g. `[4, 3]` for two sub-paths. */
  numPoints: number[];
  /** True for polygon rings, false for open polylines. */
  isClosed: boolean;
}

/** Minimum points a sub-path needs to exist, per the backend validator. */
export const MIN_POINTS_CLOSED = 3;
export const MIN_POINTS_OPEN = 2;

export function minPointsFor(isClosed: boolean): number {
  return isClosed ? MIN_POINTS_CLOSED : MIN_POINTS_OPEN;
}

/** Konva node names, shared by the renderer and its tests. */
export const MULTI_PATH_NODE_NAME = "pixano-multi-path";
export const MULTI_PATH_VERTEX_NAME = "pixano-multi-path-vertex";

/** Attribute carrying the local annotation id on a multi-path node. */
export const MULTI_PATH_ID_ATTR = "pixanoMultiPathId";

/** Tool ids, referenced by the toolbar and by tests. */
export const DRAW_POLYGON_TOOL_ID = "draw-polygon";
export const DRAW_POLYLINE_TOOL_ID = "draw-polyline";
