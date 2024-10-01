/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { createObjectInputsSchema } from "../settings/objectValidationSchemas";
import {
  Entity,
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

export const createFeature = (entity: Entity): Feature[] => {
  //filter features from entity.data (without *_ref)
  //Note: it's kinda complex to extract base keys from type... so let's make it simple and static
  const standardEntityKeys = ["item_ref", "view_ref", "parent_ref"];
  const extraFields = Object.keys(entity.data).filter(key => !standardEntityKeys.includes(key));
  const features: ItemFeature[] = [];
  //TODO : extract correct dtype from value...
  for (const field of extraFields) features.push({name: field, dtype: "str", value: entity.data[field]});
  const parsedFeatures = createObjectInputsSchema.parse(
    Object.values(features).map((feature) => ({
      ...feature,
      type: feature.dtype as Feature["type"],
      required: false,
      label: feature.name,
    })),
  );
  return parsedFeatures.map((feature) => {
    const value = entity.data[feature.name];
    if (feature.type === "list")
      return { ...feature, options: feature.options, value } as ListFeature;
    return { ...feature, value } as IntFeature | FloatFeature | TextFeature | CheckboxFeature;
  });
};

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
