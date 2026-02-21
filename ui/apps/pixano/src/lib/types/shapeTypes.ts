/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { MaskSvgPaths, MaskData, Reference } from "./dataset";
import type { PolygonEdgeHint, PolygonOutputMode } from "./tools";

export type { PolygonEdgeHint, PolygonOutputMode };

// ─── ShapeType ─────────────────────────────────────────────────────────────────

export enum ShapeType {
  none = "none",
  bbox = "bbox",
  keypoints = "keypoints",
  mask = "mask",
  polygon = "polygon",
  tracklet = "tracklet",
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
  keypoints: KeypointGraph;
};

export type SaveRectangleShape = SaveShapeBase & {
  type: ShapeType.bbox;
  attrs: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
};

export type SaveMaskShape = SaveShapeBase & {
  type: ShapeType.mask;
  masksImageSVG: MaskSvgPaths;
  rle: MaskData;
  polygonMode?: PolygonOutputMode;
  polygonPoints?: PolygonVertex[][];
};

export type SavePolygonShape = SaveShapeBase & {
  type: ShapeType.polygon;
  polygonMode: PolygonOutputMode;
  masksImageSVG: string[];
  polygonPoints: PolygonVertex[][];
  rle?: MaskData;
};

export type SaveTrackletShape = SaveShapeBase & {
  type: ShapeType.tracklet;
  attrs: {
    start_timestep: number;
    end_timestep: number;
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
  | SaveKeyBoxShape
  | SaveTrackletShape
  | TextSpanShape;

// ─── Idle State ────────────────────────────────────────────────────────────────

export type IdleState = {
  status: "none";
  shouldReset?: boolean;
};

// ─── Vertex Types ──────────────────────────────────────────────────────────────

export type PolygonVertex = {
  x: number;
  y: number;
  id: number;
};

export type KeypointVisibility = "hidden" | "visible" | "invisible";

export type KeypointVertex = {
  x: number;
  y: number;
  features?: {
    state?: KeypointVisibility;
    label?: string;
    color?: string;
  };
};

export type KeypointGraph = {
  id: string;
  template_id: string;
  viewRef?: Reference;
  entityRef?: Reference;
  edges: [number, number][];
  vertices: Required<KeypointVertex>[];
  ui?: {
    frame_index?: number;
    displayControl: import("./dataset").DisplayControl;
    startRef?: KeypointGraph;
    top_entities?: import("./dataset").Entity[];
  };
  table_info?: import("./dataset").TableInfo;
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
  keypoints: KeypointGraph;
};

export type CreatePolygonShape = {
  status: "creating";
  type: ShapeType.polygon;
  points: PolygonVertex[];
  closedPolygons: PolygonVertex[][];
  phase: "drawing" | "editing";
  viewRef: Reference;
  current?: { readonly x: number; readonly y: number };
  hoveredEdge?: PolygonEdgeHint | null;
  outputMode?: PolygonOutputMode;
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

export type CreateShape = CreatePolygonShape | CreateRectangleShape | CreateKeypointShape;

// ─── Edit Shape Types ──────────────────────────────────────────────────────────

export type EditMaskShape = {
  type: ShapeType.mask;
  counts: number[];
};

export type EditPolygonShape = {
  type: ShapeType.polygon;
  counts?: number[];
  masksImageSVG?: string[];
  polygonPoints?: PolygonVertex[][];
};

export type EditRectangleShape = {
  type: ShapeType.bbox;
  coords: number[];
};

export type EditKeypointsShape = {
  type: ShapeType.keypoints;
  vertices: KeypointGraph["vertices"];
};

export type EditShape = {
  status: "editing";
  shapeId: string;
  viewRef: Reference;
  highlighted?: "all" | "self" | "none";
  top_entity_id?: string;
} & (EditRectangleShape | EditMaskShape | EditPolygonShape | EditKeypointsShape | { type: "none" });

// ─── Shape Union ───────────────────────────────────────────────────────────────

export type Shape = SaveShape | IdleState | EditShape | CreateShape;

// ─── Feature Values ────────────────────────────────────────────────────────────

export type FeatureValues = string | number | boolean;
