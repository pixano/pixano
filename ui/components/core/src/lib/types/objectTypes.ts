import type { SegmentationResult } from ".";
import type { BBox, Mask } from "./datasetTypes";

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
  type: "keyPoint";
  keyPoints: KeyPoints;
};

export type SaveRectangleShape = SaveShapeBase & {
  type: "rectangle";
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

export type KeyPoint = {
  x: number;
  y: number;
  id: number;
  origin_points: number[];
};

export type BasePoint = {
  x: number;
  y: number;
  features: string[];
};

export type KeyPoints = {
  vertices: BasePoint[];
  edges: [number, number][];
};

export type CreateKeyPointShape = {
  status: "creating";
  type: "keyPoint";
  viewId: string;
  x: number;
  y: number;
  width: number;
  height: number;
  keyPoints: KeyPoints;
};

export type CreateMaskShape = {
  status: "creating";
  type: "mask";
  points: PolygonGroupPoint[];
  viewId: string;
};

export type CreateRectangleShape = {
  status: "creating";
  type: "rectangle";
  x: number;
  y: number;
  width: number;
  height: number;
  viewId: string;
};

export type CreateShape = CreateMaskShape | CreateRectangleShape | CreateKeyPointShape;

export type EditMaskShape = {
  type: "mask";
  counts: number[];
};

export type EditRectangleShape = {
  type: "rectangle";
  coords: number[];
};

export type EditShape = {
  status: "editing";
  shapeId: string;
  highlighted?: "all" | "self" | "none";
} & (EditRectangleShape | EditMaskShape | { type: "none" });

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
