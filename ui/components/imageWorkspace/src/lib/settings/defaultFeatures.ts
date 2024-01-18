import type { ItemFeature } from "@pixano/core";

export const DEFAULT_FEATURE = "category";

export const defaultObjectFeatures = {
  [DEFAULT_FEATURE]: {
    name: "category",
    dtype: "str",
    label: "category",
  },
};

export const defaultSceneFeatures: Record<string, ItemFeature> = {
  label: {
    name: "label",
    dtype: "str",
    value: "None",
  },
};
