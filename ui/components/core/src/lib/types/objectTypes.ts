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

type TextProperty = {
  type: "text";
  value?: string[];
  multiple?: boolean;
};

type NumberProperty = {
  type: "number";
  value?: number;
};

type CheckboxProperty = {
  type: "checkbox";
  value?: boolean;
};

export type ObjectProperty = (TextProperty | NumberProperty | CheckboxProperty) & {
  label: string;
  mandatory?: boolean;
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

type BaseObjectContent = {
  name: string;
  id: string;
  properties: ObjectProperty[];
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
