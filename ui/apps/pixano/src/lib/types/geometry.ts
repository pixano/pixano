/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** Remove readonly from all properties. For canvas/editing code that mutates geometry. */
export type Mutable<T> = { -readonly [K in keyof T]: T[K] };

/** 2D point in image coordinates. Origin: top-left. x->right, y->down. */
export interface Point2D {
  readonly x: number;
  readonly y: number;
}

/** Dimensions of a 2D raster (image, mask, canvas). */
export interface Size2D {
  readonly width: number;
  readonly height: number;
}

/** Axis-aligned bounding box. (x,y) = top-left corner, COCO/VOC xywh convention. */
export interface BoundingBox {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

/** A point with an integer index, used as a vertex in ordered collections. */
export interface IndexedPoint2D extends Point2D {
  readonly id: number;
}

/**
 * A simple polygon: ordered list of vertices forming a closed boundary.
 * The last vertex implicitly connects to the first (no need to repeat it).
 * Vertices are in image pixel coordinates.
 */
export type Polygon = readonly Point2D[];

/**
 * A polygon with holes.
 * - outer: the external boundary (counterclockwise by convention).
 * - holes: zero or more internal boundaries (clockwise by convention).
 */
export interface PolygonWithHoles {
  readonly outer: Polygon;
  readonly holes: readonly Polygon[];
}

/** A collection of polygons (multi-polygon). */
export type MultiPolygon = readonly Polygon[];

/**
 * A keypoint graph: the pure geometric primitive.
 *
 * - vertices: 2D point positions (array index = vertex index)
 * - edges: pairs of vertex indices defining the skeleton topology
 *
 * This is ONLY geometry (position + topology).
 * Per-vertex metadata (visibility, label, color) is NOT part of this type.
 */
export interface KeypointGraph {
  readonly vertices: readonly Point2D[];
  readonly edges: readonly (readonly [number, number])[];
}

/**
 * Keypoint visibility following COCO convention:
 *   "hidden"    -> not in image (COCO v=0)
 *   "invisible" -> in image but occluded (COCO v=1)
 *   "visible"   -> in image and visible (COCO v=2)
 */
export type KeypointVisibility = "hidden" | "visible" | "invisible";

/**
 * Annotation metadata for a single keypoint vertex.
 * Separate from geometry -- this is rendering/semantic information.
 */
export interface KeypointVertexMetadata {
  readonly state: KeypointVisibility;
  readonly label: string;
  readonly color: string;
}

/** A click with a binary label for interactive segmentation (SAM). 1=positive, 0=negative. */
export interface LabeledClick extends Point2D {
  readonly label: number;
}

/** Projected point on a polygon edge, for hover/insertion hints during editing. */
export interface PolygonEdgeHint extends Point2D {
  readonly shapeIndex: number;
  readonly afterIndex: number;
}

/** Polygon output format: raw polygon vertices or rasterized mask. */
export type PolygonOutputMode = "polygon" | "mask";
