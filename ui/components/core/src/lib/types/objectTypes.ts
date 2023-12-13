import type { BBox, Mask } from "./interfaces";

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

export type Shape = RectangleShape & {
  status: "creating" | "editing" | "done";
  viewId: string;
  itemId: string;
  imageWidth: number;
  imageHeight: number;
};

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
