/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { MaskData, Reference } from "./dataset";
import type {
  BoundingBox,
  IndexedPoint2D,
  KeypointGraph as KeypointSkeleton,
  KeypointVertexMetadata,
  KeypointVisibility,
  Mutable,
  Point2D,
  PolygonEdgeHint,
  PolygonOutputMode,
} from "./geometry";
import type { MaskBounds } from "$lib/utils/maskUtils";

// ─── ShapeType ─────────────────────────────────────────────────────────────────

export enum ShapeType {
  none = "none",
  bbox = "bbox",
  keypoints = "keypoints",
  mask = "mask",
  polygon = "polygon",
  polyline = "polyline",
  track = "track",
  textSpan = "textSpan",
}

// ─── Image Filters ─────────────────────────────────────────────────────────────

export interface ImageFilters {
  readonly brightness: number;
  readonly contrast: number;
  readonly equalizeHistogram: boolean;
  readonly redRange: readonly [number, number];
  readonly greenRange: readonly [number, number];
  readonly blueRange: readonly [number, number];
  readonly u16BitRange: readonly [number, number];
}

// ─── Vertex Types ──────────────────────────────────────────────────────────────

/** Mutable polygon vertex for canvas/editing code. */
export type PolygonVertex = Mutable<IndexedPoint2D>;

/**
 * A keypoint vertex combining position and per-vertex metadata.
 * Used in editing/rendering components that need both position and features together.
 */
export type KeypointVertex = Mutable<Point2D> & {
  features: {
    state: KeypointVisibility;
    label: string;
    color: string;
  };
};

// ─── Keypoint Annotation ──────────────────────────────────────────────────────

/**
 * A keypoint annotation: geometry + identity + metadata + rendering state.
 *
 * The pure geometric primitive (vertices + edges) lives in `graph`.
 * Per-vertex annotation metadata (visibility, label, color) lives in `vertexMetadata`.
 */
export type KeypointAnnotation = {
  id: string;
  template_id: string;
  viewRef?: Reference;
  entityRef?: Reference;
  graph: KeypointSkeleton;
  vertexMetadata: Mutable<KeypointVertexMetadata>[];
  ui?: {
    frame_index?: number;
    displayControl: import("./dataset").DisplayControl;
    startRef?: KeypointAnnotation;
    top_entities?: import("./dataset").Entity[];
  };
  table_info?: import("./dataset").TableInfo;
};

// ─── Save Shape Types ──────────────────────────────────────────────────────────

export type SaveShapeBase = {
  viewRef: Reference;
  itemId: string;
  imageWidth: number;
  imageHeight: number;
  status: "saving";
};

export type SaveKeyBoxShape = SaveShapeBase & {
  type: ShapeType.keypoints;
  keypoints: KeypointAnnotation;
};

export type SaveRectangleShape = SaveShapeBase & {
  type: ShapeType.bbox;
  attrs: Mutable<BoundingBox>;
};

export type SaveMaskShape = SaveShapeBase & {
  type: ShapeType.mask;
  maskDataUrl: string;
  maskMimeType?: string;
  maskBlob?: Blob;
  maskBounds?: MaskBounds;
  rle?: MaskData;
  polygonMode?: PolygonOutputMode;
  polygonPoints?: PolygonVertex[][];
};

export type SavePolygonShape = SaveShapeBase & {
  type: ShapeType.polygon;
  polygonMode: PolygonOutputMode;
  polygonPoints: PolygonVertex[][];
  isClosed: true;
  maskDataUrl?: string;
  maskMimeType?: string;
  maskBlob?: Blob;
  maskBounds?: MaskBounds;
  rle?: MaskData;
};

export type SavePolylineShape = SaveShapeBase & {
  type: ShapeType.polyline;
  polylinePoints: PolygonVertex[][];
  isClosed: false;
};

export type SaveTrackShape = SaveShapeBase & {
  type: ShapeType.track;
  attrs: {
    start_frame: number;
    end_frame: number;
    start_timestamp?: number;
    end_timestamp?: number;
  };
};

export type TextSpanAttributes = {
  mention: string;
  spans_start: number[];
  spans_end: number[];
};

export type TextSpanShape = SaveShapeBase & {
  type: ShapeType.textSpan;
  attrs: TextSpanAttributes;
};

export type SaveShape =
  | SaveRectangleShape
  | SaveMaskShape
  | SavePolygonShape
  | SavePolylineShape
  | SaveKeyBoxShape
  | SaveTrackShape
  | TextSpanShape;

// ─── Idle State ────────────────────────────────────────────────────────────────

export type IdleState = {
  status: "none";
  shouldReset?: boolean;
  resetReason?: "save-confirmed" | "save-cancelled";
  resetShapeType?: ShapeType;
  resetViewRef?: Reference;
};

// ─── Create Shape Types ────────────────────────────────────────────────────────

export type CreateKeypointShape = {
  status: "creating";
  type: ShapeType.keypoints;
  viewRef: Reference;
  x: number;
  y: number;
  width: number;
  height: number;
  keypoints: KeypointAnnotation;
};

export type CreatePolygonShape = {
  status: "creating";
  type: ShapeType.polygon;
  points: PolygonVertex[];
  closedPolygons: PolygonVertex[][];
  phase: "drawing" | "editing";
  viewRef: Reference;
  current?: Point2D;
  hoveredEdge?: PolygonEdgeHint | null;
  outputMode?: PolygonOutputMode;
};

export type CreatePolylineShape = {
  status: "creating";
  type: ShapeType.polyline;
  points: PolygonVertex[];
  closedPolygons: PolygonVertex[][];
  phase: "drawing" | "editing";
  viewRef: Reference;
  current?: Point2D;
  hoveredEdge?: PolygonEdgeHint | null;
};

export type CreateRectangleShape = {
  status: "creating";
  type: ShapeType.bbox;
  x: number;
  y: number;
  width: number;
  height: number;
  viewRef: Reference;
};

export type CreateShape =
  | CreatePolygonShape
  | CreatePolylineShape
  | CreateRectangleShape
  | CreateKeypointShape;

// ─── Edit Shape Types ──────────────────────────────────────────────────────────

export type EditMaskShape = {
  type: ShapeType.mask;
  counts: number[];
};

export type EditPolygonShape = {
  type: ShapeType.polygon;
  counts?: number[];
  polygonPoints?: PolygonVertex[][];
};

export type EditPolylineShape = {
  type: ShapeType.polyline;
  polylinePoints?: PolygonVertex[][];
};

export type EditRectangleShape = {
  type: ShapeType.bbox;
  coords: number[];
};

export type EditKeypointsShape = {
  type: ShapeType.keypoints;
  vertices: KeypointVertex[];
};

export type EditShape = {
  status: "editing";
  shapeId: string;
  viewRef: Reference;
  highlighted?: "all" | "self" | "none";
  top_entity_id?: string;
} & (
  | EditRectangleShape
  | EditMaskShape
  | EditPolygonShape
  | EditPolylineShape
  | EditKeypointsShape
  | { type: "none" }
);

// ─── Shape Union ───────────────────────────────────────────────────────────────

export type Shape = SaveShape | IdleState | EditShape | CreateShape;

// ─── Feature Values ────────────────────────────────────────────────────────────

export type FeatureValues = string | number | boolean;
