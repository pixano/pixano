/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as ort from "onnxruntime-web";
import { z } from "zod";

import {
  Annotation,
  Entity,
  Item,
  WorkspaceType,
  type FeaturesValues,
  type FeatureValues,
} from "@pixano/core";

import type {
  createObjectInputsSchema,
  listInputSchema,
  otherInputSchema,
} from "../settings/objectValidationSchemas";

export type ListInput = z.infer<typeof listInputSchema>;

export type OtherInput = z.infer<typeof otherInputSchema>;

export type CreateObjectInputs = z.infer<typeof createObjectInputsSchema>;

export type ObjectProperties = { [tableName: string]: { [featName: string]: FeatureValues } };

export type CreateObjectSchemaDefinition = Record<string, z.ZodTypeAny>;
export type CreateObjectSchema = z.ZodObject<CreateObjectSchemaDefinition>;

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
  //mainFeatures: DatasetItem["features"]; // feature;
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
export type ObjectsFilter = {
  logicOperator: LogicOperator;
  table: string;
  name: string;
  fieldOperator: FieldOperator;
  value: string | boolean;
};
