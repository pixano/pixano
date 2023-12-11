import type { z } from "zod";

import type { BBox, Mask, ItemObject } from "@pixano/core";

import { textInputSchema } from "../settings/objectSetting";
import { GROUND_TRUTH, MODEL_RUN } from "../constants";

export type ObjectTextInput = z.infer<typeof textInputSchema>;

export type ObjectsSortedByModelType = {
  [GROUND_TRUTH]: ItemObject[];
  [MODEL_RUN]: { modelName: string; objects: ItemObject[] }[];
};

type BaseObjectContent = {
  name: string;
  id: string;
  properties: {
    label: string[];
  };
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
