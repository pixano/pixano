/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Entity, ItemFeature } from "@pixano/core";

// TextSpan features to use (value) instead of "mention"
export const DISPLAY_MENTION_FEATURES = ["role"];

// default entity features used to display tooltip, in this order
const DEFAULT_FEATURES = ["name", "category", "category_name"];

export const getDefaultDisplayFeat = (entity: Entity): string | null => {
  for (const default_feature of DEFAULT_FEATURES) {
    if (default_feature in entity.data) {
      return String(entity.data[default_feature]);
    }
  }
  return null;
};

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
