/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ItemFeature } from "@pixano/core";

// default features used to display tooltip, in this order
export const DEFAULT_FEATURES = ["name", "category", "category_name"];

export const defaultObjectFeatures = {
  [DEFAULT_FEATURES[0]]: {
    name: "name",
    dtype: "str",
    label: "name",
  },
};

export const defaultSceneFeatures: Record<string, ItemFeature> = {
  label: {
    name: "label",
    dtype: "str",
    value: "None",
  },
};
