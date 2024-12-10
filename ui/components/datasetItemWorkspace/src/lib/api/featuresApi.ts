/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  Annotation,
  BaseSchema,
  Entity,
  Item,
  type DatasetSchema,
  type FeatureList,
  type FeaturesValues,
  type ItemFeature,
} from "@pixano/core";
import { createObjectInputsSchema } from "../settings/objectValidationSchemas";
import type {
  CheckboxFeature,
  CreateObjectInputs,
  Feature,
  FloatFeature,
  IntFeature,
  ListFeature,
  ObjectProperties,
  TextFeature,
} from "../types/datasetItemWorkspaceTypes";

export function createFeature(
  obj: Item | Entity | Annotation,
  dataset_schema: DatasetSchema,
  additional_info: string = "",
): Feature[] {
  const extraFields = obj.getDynamicFields();
  const extraFieldsType = extraFields.reduce(
    (acc, key) => {
      acc[key] = dataset_schema.schemas[obj.table_info.name].fields[key]?.type || "str";
      return acc;
    },
    {} as Record<string, string>,
  );
  const features: ItemFeature[] = [];
  if (extraFields.length > 0) {
    for (const field of extraFields)
      features.push({
        name: field,
        dtype: extraFieldsType[field],
        value: (obj.data as Record<string, unknown>)[field],
      } as ItemFeature);
  }
  const display_info = additional_info !== "" ? "[" + additional_info + "] " : "";
  const parsedFeatures = createObjectInputsSchema.parse(
    Object.values(features).map((feature) => ({
      ...feature,
      type: feature.dtype,
      required: false,
      sch: { name: "", group: "", base_schema: BaseSchema.Feature }, //not used here, we will pass obj below
      label: `${display_info}${feature.name}`, //TMP //TODO WIP -- group display by table_info.name (&view?)
    })),
  );
  return parsedFeatures.map((feature) => {
    const value = (obj.data as Record<string, unknown>)[feature.name] as string; //TODO? type (feature.type to type)
    if (feature.type === "list")
      return { ...feature, options: feature.options, value, obj } as ListFeature;
    return { ...feature, value, obj } as IntFeature | FloatFeature | TextFeature | CheckboxFeature;
  });
}

export const mapShapeInputsToFeatures = (
  shapeInputs: ObjectProperties,
  formInputs: CreateObjectInputs,
) => {
  const features: Record<string, Record<string, ItemFeature>> = {};
  Object.entries(shapeInputs).forEach(([tname, feats]) => {
    features[tname] = Object.entries(feats).reduce(
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
  });
  return features;
};

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
