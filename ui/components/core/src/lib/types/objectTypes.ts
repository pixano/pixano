import type { BBox, Mask } from "./interfaces";

// ObjectContent --> objet deja créé
// Shape -> objet en cours de création
// ObjectParameters --> paramètres d'une shape puis d'un objet

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

// SHAPES: shapes drawn on the image to yet saved as objects
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
};

export type PropertiesValues = string[] | number | boolean;

type BaseObjectContent = {
  name: string;
  id: string;
  properties: Record<string, PropertiesValues>;
  editing?: boolean;
};

export type BoxObjectContent = {
  type: "box";
  boundingBox: BBox;
};

export type MaskObjectContent = {
  type: "mask";
  mask: Mask;
};

export type ObjectContent = BaseObjectContent & (BoxObjectContent | MaskObjectContent);
