/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { type DatasetSchema, type FeaturesValues } from "$lib/types/dataset";

type BackFeatureValue = {
  name: string;
  restricted: boolean;
  values: string[];
};
type BackFeatureValues = Record<string, Record<string, BackFeatureValue[]>>;

export function mapFeatureValues(rawFeatureValues: object, schema: DatasetSchema): FeaturesValues {
  const feature_values = rawFeatureValues as BackFeatureValues;
  const frontFV: FeaturesValues = { main: {}, objects: {} };

  if ("item" in feature_values && feature_values["item"] && feature_values["item"]["item"]) {
    for (const feat of feature_values["item"]["item"]) {
      const { name, ...fv } = feat;
      frontFV.main[name] = fv;
    }
  }
  if (
    "entities" in feature_values &&
    feature_values["entities"] &&
    Object.keys(feature_values["entities"]).length > 0
  ) {
    for (const entity_group of schema.groups.entities) {
      if (feature_values["entities"][entity_group]) {
        for (const feat of feature_values["entities"][entity_group]) {
          const { name, ...fv } = feat;
          frontFV.objects[name] = fv;
        }
      }
    }
  }
  if (
    "annotations" in feature_values &&
    feature_values["annotations"] &&
    Object.keys(feature_values["annotations"]).length > 0
  ) {
    for (const ann_group of schema.groups.annotations) {
      if (feature_values["annotations"][ann_group]) {
        for (const feat of feature_values["annotations"][ann_group]) {
          const { name, ...fv } = feat;
          frontFV.objects[name] = fv;
        }
      }
    }
  }

  return frontFV;
}
