/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { SegmentationResult } from ".";
import type { BBox, DisplayControl, Entity, Mask, Reference } from "./dataset";

// OBJECTS FEATURES
export type TextFeature = {
  type: "str";
  multiple: boolean;
  value: string;
};

export type SaveShapeBase = {
  viewRef: Reference;
  itemId: string;
  imageWidth: number;
  imageHeight: number;
  status: "saving";
};

export enum SaveShapeType {
  bbox = "bbox",
  keypoints = "keypoints",
  mask = "mask",
  tracklet = "tracklet",
  textSpan = "textSpan",
}

export type SaveKeyBoxShape = SaveShapeBase & {
  type: SaveShapeType.keypoints;
  keypoints: KeypointsTemplate;
};

export type SaveRectangleShape = SaveShapeBase & {
  type: SaveShapeType.bbox;
  attrs: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
};

type SaveMaskShape = SegmentationResult &
  SaveShapeBase & {
    type: SaveShapeType.mask;
  };

export type SaveTrackletShape = SaveShapeBase & {
  type: SaveShapeType.tracklet;
  attrs: {
    start_timestep: number;
    end_timestep: number;
    start_timestamp?: number;
    end_timestamp?: number;
  };
};

export type TextSpanShape = SaveShapeBase & {
  type: SaveShapeType.textSpan;
  attrs: {
    mention: string;
    spans_start: number[];
    spans_end: number[];
  };
};

export type SaveShape =
  | SaveRectangleShape
  | SaveMaskShape
  | SaveKeyBoxShape
  | SaveTrackletShape
  | TextSpanShape;

export type noShape = {
  status: "none";
  shouldReset?: boolean;
};

export type PolygonGroupPoint = {
  x: number;
  y: number;
  id: number;
};

export type VertexStates = "hidden" | "visible" | "invisible";

export type Vertex = {
  x: number;
  y: number;
  features?: {
    state?: VertexStates;
    label?: string;
    color?: string;
  };
};

export type KeypointsTemplate = {
  id: string;
  template_id: string;
  viewRef?: Reference;
  entityRef?: Reference;
  edges: [number, number][];
  vertices: Required<Vertex>[];
  ui?: {
    frame_index?: number;
    displayControl?: DisplayControl;
    highlighted?: "all" | "self" | "none";
    startRef?: KeypointsTemplate;
    top_entities?: Entity[];
  };
};

export type CreateKeypointShape = {
  status: "creating";
  type: SaveShapeType.keypoints;
  viewRef: Reference;
  x: number;
  y: number;
  width: number;
  height: number;
  keypoints: KeypointsTemplate;
};

export type CreateMaskShape = {
  status: "creating";
  type: SaveShapeType.mask;
  points: PolygonGroupPoint[];
  viewRef: Reference;
};

export type CreateRectangleShape = {
  status: "creating";
  type: SaveShapeType.bbox;
  x: number;
  y: number;
  width: number;
  height: number;
  viewRef: Reference;
};

export type CreateShape = CreateMaskShape | CreateRectangleShape | CreateKeypointShape;

export type EditMaskShape = {
  type: SaveShapeType.mask;
  counts: number[];
};

export type EditRectangleShape = {
  type: SaveShapeType.bbox;
  coords: number[];
};

export type EditKeypointsShape = {
  type: SaveShapeType.keypoints;
  vertices: KeypointsTemplate["vertices"];
};

export type EditShape = {
  status: "editing";
  shapeId: string;
  viewRef: Reference;
  highlighted?: "all" | "self" | "none";
  top_entity_id?: string;
} & (EditRectangleShape | EditMaskShape | EditKeypointsShape | { type: "none" });

export type Shape = SaveShape | noShape | EditShape | CreateShape;

export type FeatureValues = string | number | boolean;

type BaseObjectContent = {
  name: string;
  id: string;
  properties: Record<string, FeatureValues>;
  editing?: boolean;
};

export type BoxObjectContent = BaseObjectContent & {
  type: "box";
  boundingBox: BBox;
};

export type MaskObjectContent = BaseObjectContent & {
  type: "mask";
  mask: Mask;
};

export type ObjectContent = BoxObjectContent | MaskObjectContent;
