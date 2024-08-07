/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { SegmentationResult } from ".";
import type { BBox, DisplayControl, Mask } from "./datasetTypes";

// OBJECTS FEATURES
export type TextFeature = {
  type: "str";
  multiple: boolean;
  value: string;
};

export type SaveShapeBase = {
  viewId: string;
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

export type SaveShape = SaveRectangleShape | SaveMaskShape | SaveKeyBoxShape;

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

export type Keypoints = {
  id: string;
  view_id?: string;
  template_id: string;
  vertices: Vertex[];
  displayControl?: DisplayControl;
};

export type KeypointsTemplate = {
  id: string;
  view_id?: string;
  edges: [number, number][];
  vertices: Required<Vertex>[];
  editing?: boolean;
  visible?: boolean;
  displayControl?: DisplayControl;
  highlighted?: "all" | "self" | "none";
};

export type CreateKeypointShape = {
  status: "creating";
  type: "keypoints";
  viewId: string;
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
  viewId: string;
};

export type CreateRectangleShape = {
  status: "creating";
  type: "bbox";
  x: number;
  y: number;
  width: number;
  height: number;
  viewId: string;
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
  viewId: string;
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
