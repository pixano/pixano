/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Per-point status, mirroring the backend's `KeyPoints.states` validator —
 * anything outside these three is rejected server-side.
 */
export type KeypointState = "visible" | "invisible" | "hidden";

/**
 * Geometry of a keypoint skeleton, held as the backend stores it.
 *
 * `coords` is a flat, normalized `[x0, y0, x1, y1, …]` list — same [0,1]
 * convention as a bbox, so the skeleton survives a display resize. It is a
 * plain `number[]` rather than a tuple on purpose: the length is the template's
 * point count, which varies per template and is not known at compile time.
 *
 * Invariants the backend enforces and the seed loader re-checks: an even number
 * of coords, one state per point, and no negative coordinate.
 */
export interface KeypointsGeometry {
  /** Which skeleton this is; resolves to edges and labels via the registry. */
  templateId: string;
  coords: number[];
  states: KeypointState[];
}

/** Konva node names, shared by the renderer and its tests. */
export const KEYPOINTS_VERTEX_NAME = "pixano-keypoint-vertex";
export const KEYPOINTS_EDGE_NAME = "pixano-keypoint-edge";

/** Attribute carrying the local annotation id on a keypoints node. */
export const KEYPOINTS_ID_ATTR = "pixanoKeypointsId";

/**
 * Attribute carrying a vertex's index into the skeleton's point list. Needed
 * because hidden points get no circle, so a handle's position among the drawn
 * vertices is not its index in `coords`.
 */
export const KEYPOINTS_VERTEX_INDEX_ATTR = "pixanoKeypointIndex";

/** Tool id of the skeleton placer, referenced by the toolbar and by tests. */
export const DRAW_KEYPOINTS_TOOL_ID = "draw-keypoints";
