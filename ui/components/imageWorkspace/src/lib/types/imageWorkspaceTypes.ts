import { z } from "zod";

import type { ItemObject } from "@pixano/core";

import { GROUND_TRUTH, MODEL_RUN } from "../constants";
import type { listInputSchema, otherInputSchema } from "../settings/objectValidationSchemas";

export type ListInput = z.infer<typeof listInputSchema>;

export type OtherInput = z.infer<typeof otherInputSchema>;

export type ObjectsSortedByModelType = {
  [GROUND_TRUTH]: ItemObject[];
  [MODEL_RUN]: { modelName: string; objects: ItemObject[] }[];
};

type CheckboxFeature = OtherInput & {
  type: "boolean";
  value: boolean;
};

export type TextFeature = OtherInput & {
  type: "text";
  value: string;
};

export type NumberFeature = OtherInput & {
  type: "number";
  value: number;
};

export type ListFeature = ListInput & {
  value: string;
};

export type Feature = CheckboxFeature | TextFeature | NumberFeature | ListFeature;
