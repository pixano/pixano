/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { createObjectInputsSchema } from "../settings/objectValidationSchemas";
import {
  BaseData,
  type FeatureValues,
  type ItemFeature,
  type FeaturesValues,
  type FeatureList,
} from "@pixano/core";
import type {
  CheckboxFeature,
  CreateObjectInputs,
  Feature,
  ListFeature,
  IntFeature,
  FloatFeature,
  TextFeature,
} from "../types/datasetItemWorkspaceTypes";

export function createFeature(obj: BaseData<Any>, defaultFeats: Feature[] = []): Feature[] {
  const extraFields = obj.getDynamicFields();
  let features: Feature[] = [];
  if (extraFields.length > 0) {
    //TODO : extract correct dtype from value... (or better: from schema)
    for (const field of extraFields)
      features.push({ name: field, dtype: "str", value: obj.data[field] as string }); //TODO type
  } else {
    features = defaultFeats;
  }
  const parsedFeatures = createObjectInputsSchema.parse(
    Object.values(features).map((feature) => ({
      ...feature,
      type: feature.dtype as Feature["type"],
      required: false,
      label: feature.name,
    })),
  );
  return parsedFeatures.map((feature) => {
    const value = obj.data[feature.name] as string; //TODO type
    if (feature.type === "list")
      return { ...feature, options: feature.options, value } as ListFeature;
    return { ...feature, value } as IntFeature | FloatFeature | TextFeature | CheckboxFeature;
  });
}

export const mapShapeInputsToFeatures = (
  shapeInputs: { [key: string]: FeatureValues },
  formInputs: CreateObjectInputs,
) =>
  Object.entries(shapeInputs).reduce(
    (acc, [key, value]) => {
      acc[key] = {
        name: key,
        dtype: formInputs.find((o) => o.name === key)?.type as ItemFeature["dtype"],
        value,
      };
      return acc;
    },
    {} as Record<string, ItemFeature>,
  );

export const addNewInput = (
  store: FeaturesValues | undefined,
  feature_class: string,
  feature: string,
  value: string,
) => {
  if (store) {
    // add new inputs to lists of available values
    if (feature_class === "objects" || feature_class === "main") {
      if (!store[feature_class][feature]) {
        store[feature_class][feature] = { restricted: false, values: [value] };
      } else if (!store[feature_class][feature].values.includes(value)) {
        store[feature_class][feature].values.push(value);
      }
    }
  }
};
export const mapFeatureList = (featureList: FeatureList = { restricted: false, values: [] }) => {
  featureList.values ??= [];
  featureList.restricted ??= false;
  return featureList.values
    .sort((a, b) => a.localeCompare(b))
    .map((value) => ({
      value,
      label: value,
    }));
};
