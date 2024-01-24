import { z } from "zod";
import * as ort from "onnxruntime-web";

import type { ItemObject } from "@pixano/core";

import { GROUND_TRUTH, MODEL_RUN, PRE_ANNOTATION } from "../constants";
import type {
  createObjectInputsSchema,
  listInputSchema,
  otherInputSchema,
} from "../settings/objectValidationSchemas";

export type ObjectsSortedByModelType = {
  [GROUND_TRUTH]: ItemObject[];
  [PRE_ANNOTATION]: ItemObject[];
  [MODEL_RUN]: { modelName: string; objects: ItemObject[] }[];
};

export type ListInput = z.infer<typeof listInputSchema>;

export type OtherInput = z.infer<typeof otherInputSchema>;

export type CreateObjectInputs = z.infer<typeof createObjectInputsSchema>;

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
  currentModalOpen: "selectModel" | "noModel" | "noEmbeddings" | "none";
  selectedModelName: string;
};
