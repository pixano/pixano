/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as ort from "onnxruntime-web";

import {
  Annotation,
  Entity,
  Item,
  View,
  WorkspaceType,
  type FeaturesValues,
  type Image,
  type SequenceFrame,
} from "$lib/types/dataset";
import type { FeatureValues } from "$lib/types/shapeTypes";

export type MView = Record<string, Image | SequenceFrame[]>;
export type WorkspaceViewerItem = {
  item: Item;
  views: Record<string, View | View[]>;
  ui: {
    datasetId: string;
    type: WorkspaceType;
  };
};
export type WorkspaceData = WorkspaceViewerItem & {
  entities: Record<string, Entity[]>;
  annotations: Record<string, Annotation[]>;
};

import type {
  ListInput as ListInputDef,
  OtherInput as OtherInputDef,
  InputFeatures,
} from "$lib/utils/featureValidationSchemas";

export type ListInput = ListInputDef;

export type OtherInput = OtherInputDef;

export type CreateEntityInputs = InputFeatures;

export type EntityProperties = { [tableName: string]: { [featName: string]: FeatureValues } };

export type CheckboxFeature = OtherInput & {
  type: "bool";
  value: boolean;
  obj: Item | Entity | Annotation;
};

export type TextFeature = OtherInput & {
  type: "str";
  value: string;
  obj: Item | Entity | Annotation;
};

export type NumberFeature = IntFeature | FloatFeature;

export type IntFeature = OtherInput & {
  type: "int";
  value: number;
  obj: Item | Entity | Annotation;
};

export type FloatFeature = OtherInput & {
  type: "float";
  value: number;
  obj: Item | Entity | Annotation;
};

export type ListFeature = ListInput & {
  value: string;
  obj: Item | Entity | Annotation;
};

export type Feature = CheckboxFeature | TextFeature | NumberFeature | ListFeature;

export type Embeddings = Record<string, ort.Tensor>;

export type ModelSelection = {
  currentModalOpen:
    | "selectModel"
    | "selectEmbeddingsTable"
    | "noModel"
    | "noEmbeddings"
    | "loading"
    | "none";
  selectedModelName: string;
  selectedTableName: string;
  yetToLoadEmbedding: boolean;
};

export type ItemsMeta = {
  //objectFeatures: Record<string, ItemFeature>; // itemFeatures
  featuresList: FeaturesValues;
  item: Item;
  type: WorkspaceType;
  format?: "1bit" | "8bit" | "16bit";
  color?: "grayscale" | "rgb" | "rgba";
};

export type Filters = {
  brightness: number;
  contrast: number;
  equalizeHistogram: boolean;
  redRange: number[];
  greenRange: number[];
  blueRange: number[];
  u16BitRange: number[];
};

export type Merges = {
  //reference: Entity,
  to_fuse: Entity[];
  forbids: Entity[];
};

// Filters types
export type LogicOperator = "FIRST" | "AND" | "OR";
type StrOperator = "=" | "startsWith" | "endsWith";
type BoolOperator = "=";
type NumberOperator = "=" | "<" | ">" | "<=" | ">=";
export type FieldOperator = StrOperator | BoolOperator | NumberOperator;
const strOperators: StrOperator[] = ["=", "startsWith", "endsWith"];
const boolOperators: BoolOperator[] = ["="];
const numberOperators: NumberOperator[] = ["=", "<", ">", "<=", ">="];

export function getOperatorsForType(typeVal: string): FieldOperator[] {
  switch (typeVal) {
    case "int":
    case "float":
      return numberOperators;
    case "bool":
      return boolOperators;
    default:
      return strOperators;
  }
}

export type FieldCol = { name: string; type: string };
export type EntityFilter = {
  logicOperator: LogicOperator;
  table: string;
  name: string;
  fieldOperator: FieldOperator;
  value: string | boolean;
};
