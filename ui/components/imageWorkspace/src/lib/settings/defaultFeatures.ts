import type { ItemFeature } from "@pixano/core";

export const DEFAULT_FEATURE = "category";

export const defaultObjectFeatures = {
  [DEFAULT_FEATURE]: {
    name: "category",
    dtype: "text",
    label: "category",
  },
};

export const defaultSceneFeatures: Record<string, ItemFeature> = {
  label: {
    name: "label",
    dtype: "text",
    value: "None",
  },
};
