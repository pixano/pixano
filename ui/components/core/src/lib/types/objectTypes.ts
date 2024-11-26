/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { SegmentationResult } from ".";
import type { BBox, DisplayControl, Mask, Entity, Reference } from "./datasetTypes";

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

export type SaveKeyBoxShape = SaveShapeBase & {
  type: "keypoints";
  keypoints: KeypointsTemplate;
};

export type SaveRectangleShape = SaveShapeBase & {
  type: "bbox";
  attrs: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
};

type SaveMaskShape = SegmentationResult &
  SaveShapeBase & {
    type: "mask";
  };

export type SaveTrackletShape = SaveShapeBase & {
  type: "tracklet";
  attrs: {
    start_timestep: number;
    end_timestep: number;
    start_timestamp?: number;
    end_timestamp?: number;
  };
};

export type SaveShape = SaveRectangleShape | SaveMaskShape | SaveKeyBoxShape | SaveTrackletShape;

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
  type: "keypoints";
  viewRef: Reference;
  x: number;
  y: number;
  width: number;
  height: number;
  keypoints: KeypointsTemplate;
};

export type CreateMaskShape = {
  status: "creating";
  type: "mask";
  points: PolygonGroupPoint[];
  viewRef: Reference;
};

export type CreateRectangleShape = {
  status: "creating";
  type: "bbox";
  x: number;
  y: number;
  width: number;
  height: number;
  viewRef: Reference;
};

export type CreateShape = CreateMaskShape | CreateRectangleShape | CreateKeypointShape;

export type EditMaskShape = {
  type: "mask";
  counts: number[];
};

export type EditRectangleShape = {
  type: "bbox";
  coords: number[];
};

export type EditKeypointsShape = {
  type: "keypoints";
  vertices: KeypointsTemplate["vertices"];
};

export type EditShape = {
  status: "editing";
  shapeId: string;
  viewRef: Reference;
  highlighted?: "all" | "self" | "none";
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
