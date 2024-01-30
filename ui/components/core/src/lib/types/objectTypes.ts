import type { SegmentationResult } from ".";
import type { BBox, Mask } from "./datasetTypes";

// OBJECTS FEATURES
export type TextFeature = {
  type: "str";
  multiple: boolean;
  value: string;
};

// SHAPES: shapes drawn on the image not yet saved as objects
type RectangleShape = {
  type: "rectangle";
  attrs: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
};

type MaskShape = SegmentationResult & {
  type: "mask";
  isManual?: boolean;
};

export type inProgressShape = (RectangleShape | MaskShape) & {
  viewId: string;
  itemId: string;
  imageWidth: number;
  imageHeight: number;
  status: "inProgress";
};

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
};

export type editMaskShape = {
  status: "editing";
  type: "mask";
  maskId: string;
  counts: number[];
};

export type editRectangleShape = {
  status: "editing";
  type: "rectangle";
  rectangleId: string;
  coords: number[];
};

export type Shape =
  | inProgressShape
  | noShape
  | editMaskShape
  | editRectangleShape
  | CreateMaskShape;

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
