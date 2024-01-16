import type { ItemFeature } from "@pixano/core";

export const defaultObjectFeatures = {
  category: {
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
