/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ItemFeature } from "@pixano/core";

export const DEFAULT_FEATURE = "name";

export const defaultObjectFeatures = {
  [DEFAULT_FEATURE]: {
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
