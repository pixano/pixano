/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import * as ort from "onnxruntime-web";

import { DatasetItem, type FeaturesValues, type FeatureValues } from "@pixano/core";

import { GROUND_TRUTH, PRE_ANNOTATION } from "../constants";
import type {
  createObjectInputsSchema,
  listInputSchema,
  otherInputSchema,
} from "../settings/objectValidationSchemas";

export type ObjectsSortedByModelType<T> = {
  [GROUND_TRUTH]: T[];
  [PRE_ANNOTATION]: T[];
  [key: string]: T[];
};

export type ListInput = z.infer<typeof listInputSchema>;

export type OtherInput = z.infer<typeof otherInputSchema>;

export type CreateObjectInputs = z.infer<typeof createObjectInputsSchema>;

export type ObjectProperties = { [key: string]: FeatureValues };

export type CreateObjectSchemaDefinition = Record<string, z.ZodTypeAny>;
export type CreateObjectSchema = z.ZodObject<CreateObjectSchemaDefinition>;

export type CheckboxFeature = OtherInput & {
  type: "bool";
  value: boolean;
};

export type TextFeature = OtherInput & {
  type: "str";
  value: string;
};

export type NumberFeature = IntFeature | FloatFeature;

export type IntFeature = OtherInput & {
  type: "int";
  value: number;
};

export type FloatFeature = OtherInput & {
  type: "float";
  value: number;
};

export type ListFeature = ListInput & {
  value: string;
};

export type Feature = CheckboxFeature | TextFeature | NumberFeature | ListFeature;

export type Embeddings = Record<string, ort.Tensor>;

export type ModelSelection = {
  currentModalOpen: "selectModel" | "selectEmbeddingsTable" | "noModel" | "noEmbeddings" | "none";
  selectedModelName: string;
};

export type ItemsMeta = {
  //mainFeatures: DatasetItem["features"]; // feature;
  //objectFeatures: Record<string, ItemFeature>; // itemFeatures
  featuresList: FeaturesValues;
  item: DatasetItem["item"];
  type: string;
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
