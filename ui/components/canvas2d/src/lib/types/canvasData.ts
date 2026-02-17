/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Reference } from "@pixano/document";

export type CanvasReference = Reference;

export type CanvasImage = {
  id: string;
  element: HTMLImageElement;
};

export type CanvasImagesPerView = Record<string, CanvasImage[]>;

export type CanvasMaskSVG = string[];

export interface CanvasEntityRef {
  id: string;
}

export interface CanvasTopEntity {
  id: string;
}

export interface CanvasDisplayControl {
  hidden: boolean;
  editing: boolean;
  highlighted: "all" | "self" | "none";
}

export interface CanvasAnnotationLike {
  id: string;
}

export interface CanvasBBox extends CanvasAnnotationLike {
  data: {
    coords: number[];
    entity_ref: CanvasEntityRef;
    view_ref: CanvasReference;
  };
  ui: {
    displayControl: CanvasDisplayControl;
    opacity: number;
    strokeFactor: number;
    tooltip: string;
    top_entities: CanvasTopEntity[];
  };
}

export interface CanvasMask extends CanvasAnnotationLike {
  data: {
    entity_ref: CanvasEntityRef;
    view_ref: CanvasReference;
    inference_metadata?: Record<string, unknown>;
  };
  ui: {
    displayControl: CanvasDisplayControl;
    opacity: number;
    strokeFactor: number;
    svg: CanvasMaskSVG;
    rawPoints?: Array<Array<{ x: number; y: number; id: number }>>;
    top_entities: CanvasTopEntity[];
  };
}

export type CanvasVertexState = "hidden" | "visible" | "invisible";

export interface CanvasVertex {
  x: number;
  y: number;
  features: {
    color?: string;
    label?: string;
    state?: CanvasVertexState;
  };
}

export interface CanvasKeypoints extends CanvasAnnotationLike {
  entityRef: CanvasEntityRef;
  id: string;
  viewRef: CanvasReference;
  edges: [number, number][];
  vertices: CanvasVertex[];
  ui: {
    displayControl: CanvasDisplayControl;
    top_entities?: CanvasTopEntity[];
  };
}

export const CanvasShapeType = {
  None: "none",
  BBox: "bbox",
  Polygon: "polygon",
  Mask: "mask",
  Keypoints: "keypoints",
} as const;

export type CanvasShapeStatus = "none" | "creating" | "editing" | "saving";
export type CanvasShapeKind = (typeof CanvasShapeType)[keyof typeof CanvasShapeType];

export interface CanvasShape {
  status: CanvasShapeStatus | (string & {});
  type?: CanvasShapeKind | (string & {});
  viewRef?: CanvasReference;
  shouldReset?: boolean;
  [key: string]: unknown;
}

export interface CanvasBBoxCreatingShape extends CanvasShape {
  status: "creating";
  type: typeof CanvasShapeType.BBox;
  x: number;
  y: number;
  width: number;
  height: number;
  viewRef: CanvasReference;
}

export interface CanvasBBoxSavingShape extends CanvasShape {
  status: "saving";
  type: typeof CanvasShapeType.BBox;
  attrs: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  viewRef: CanvasReference;
  itemId: string;
  imageWidth: number;
  imageHeight: number;
}

export interface CanvasMaskSavingShape extends CanvasShape {
  status: "saving";
  type: typeof CanvasShapeType.Mask;
  masksImageSVG: CanvasMaskSVG;
  rle: {
    counts: number[];
    size: [number, number];
  };
  viewRef: CanvasReference;
  itemId: string;
  imageWidth: number;
  imageHeight: number;
}

export type CanvasPolygonOutputMode = "polygon" | "mask";

export interface CanvasPolygonPoint {
  x: number;
  y: number;
  id: number;
}

export interface CanvasPolygonEdgeHint {
  x: number;
  y: number;
  shapeIndex: number;
  afterIndex: number;
}

export interface CanvasPolygonCreatingShape extends CanvasShape {
  status: "creating";
  type: typeof CanvasShapeType.Polygon;
  viewRef: CanvasReference;
  phase: "drawing" | "editing";
  closedPolygons: CanvasPolygonPoint[][];
  points: CanvasPolygonPoint[];
  current?: { x: number; y: number };
  hoveredEdge?: CanvasPolygonEdgeHint | null;
  outputMode: CanvasPolygonOutputMode;
}
