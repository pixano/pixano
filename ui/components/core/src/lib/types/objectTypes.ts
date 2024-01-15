import type { SegmentationResult } from ".";
import type { BBox, Mask } from "./datasetTypes";

export type ObjectParameters = {
  label: string;
  multiple: boolean;
  type: "text" | "number" | "checkbox";
  mandatory: boolean;
};

// OBJECTS FEATURES
export type TextFeature = {
  type: "text";
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
};

export type editMaskShape = {
  status: "editingMask";
  maskId: string;
  counts: number[];
};

export type Shape = inProgressShape | noShape | editMaskShape;

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
