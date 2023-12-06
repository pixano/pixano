import type { BBox, Mask } from "./interfaces";

export type ObjectParameters = {
  label: string;
  multiple: boolean;
  type: "text" | "number" | "checkbox";
  mandatory: boolean;
};

// OBJECTS PROPERTIES

export type TextProperty = {
  type: "text";
  multiple: boolean;
  value: string[];
};

type NumberProperty = {
  type: "number";
  value: number;
};

type CheckboxProperty = {
  type: "checkbox";
  value: boolean;
};

export type ObjectProperty = (TextProperty | NumberProperty | CheckboxProperty) & {
  label: string;
  required: boolean;
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
};

export type PropertiesValues = string[] | number | boolean;

type BaseObjectContent = {
  name: string;
  id: string;
  properties: Record<string, PropertiesValues>;
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
