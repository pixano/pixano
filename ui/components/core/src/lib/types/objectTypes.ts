import type { SegmentationResult } from ".";
import type { BBox, Mask } from "./datasetTypes";

// OBJECTS FEATURES
export type TextFeature = {
  type: "str";
  multiple: boolean;
  value: string;
};

// SHAPES: shapes drawn on the image not yet saved as objects
export type InProgressBase = {
  viewId: string;
  itemId: string;
  imageWidth: number;
  imageHeight: number;
  status: "inProgress";
};

export type InProgressRectangleShape = InProgressBase & {
  type: "rectangle";
  attrs: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
};

type MaskShape = SegmentationResult &
  InProgressBase & {
    type: "mask";
  };

export type inProgressShape = InProgressRectangleShape | MaskShape;

export type noShape = {
  status: "none";
  shouldReset?: boolean;
};

export type PolygonGroupPoint = {
  x: number;
  y: number;
  id: number;
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

export type CreateShape = CreateMaskShape | CreateRectangleShape;

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

export type Shape = inProgressShape | noShape | EditShape | CreateShape;

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
