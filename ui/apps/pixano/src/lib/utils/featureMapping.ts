/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  Annotation,
  BaseSchema,
  BBox,
  Entity,
  Item,
  Keypoints,
  Mask,
  Message,
  TextSpan,
  Tracklet,
  type FeatureList,
  type FeaturesValues,
  type ItemFeature,
} from "$lib/types/dataset";
import type {
  CheckboxFeature,
  CreateEntityInputs,
  EntityProperties,
  Feature,
  FloatFeature,
  IntFeature,
  ListFeature,
  TextFeature,
} from "$lib/types/workspace";
import type { InputFeatures } from "$lib/utils/featureValidationSchemas";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

export function createFeature(
  obj: Item | Entity | Annotation,
  workspaceManifest: WorkspaceManifest,
  additional_info: string = "",
): Feature[] {
  const extraFields = obj.getDynamicFields();
  const extraFieldsType = extraFields.reduce(
    (acc, key) => {
      acc[key] = workspaceManifest.tablesByName[obj.table_info.name]?.fields[key]?.type || "str";
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
  const parsedFeatures = Object.values(features).map((feature) => ({
    ...feature,
    type: feature.dtype as "int" | "float" | "str" | "bool" | "list" | "SourceRef",
    required: false,
    sch: { name: "", group: "", base_schema: BaseSchema.Feature }, //not used here, we will pass obj below
    label: `${display_info}${feature.name}`, //TMP //TODO WIP -- group display by table_info.name (&view?)
  })) as InputFeatures;
  return parsedFeatures.map((feature) => {
    const value = (obj.data as Record<string, unknown>)[feature.name] as string; //TODO? type (feature.type to type)
    if (feature.type === "list")
      return { ...feature, options: feature.options, value, obj } as ListFeature;
    return { ...feature, value, obj } as IntFeature | FloatFeature | TextFeature | CheckboxFeature;
  });
}

export const mapShapeInputsToFeatures = (
  shapeInputs: EntityProperties,
  formInputs: CreateEntityInputs,
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

export const getValidationSchemaAndFormInputs = (
  workspaceManifest: WorkspaceManifest,
  baseSchema: BaseSchema,
) => {
  //TODO: need to take schema relation into account (when schema relation available)
  //required when there is several differents tracks / entities / subentities for different purpose
  const featuresArray: InputFeatures = [];
  Object.entries(workspaceManifest.tablesByName).forEach(([tname, table]) => {
    const sch = { base_schema: table.baseSchema, fields: table.fields };
    let nonFeatsFields: string[] = [];
    let group = "entities";
    if ([BaseSchema.Entity, baseSchema].includes(sch.base_schema)) {
      if (baseSchema === sch.base_schema) {
        group = "annotations";
        if (baseSchema === BaseSchema.BBox)
          nonFeatsFields = nonFeatsFields.concat(BBox.nonFeaturesFields());
        if (baseSchema === BaseSchema.Keypoints)
          nonFeatsFields = nonFeatsFields.concat(Keypoints.nonFeaturesFields());
        if (baseSchema === BaseSchema.Mask)
          nonFeatsFields = nonFeatsFields.concat(Mask.nonFeaturesFields());
        if (baseSchema === BaseSchema.Tracklet)
          nonFeatsFields = nonFeatsFields.concat(Tracklet.nonFeaturesFields());
        if (baseSchema === BaseSchema.TextSpan)
          nonFeatsFields = nonFeatsFields.concat(TextSpan.nonFeaturesFields());
        if (baseSchema === BaseSchema.Message)
          nonFeatsFields = nonFeatsFields.concat(Message.nonFeaturesFields());
      } else {
        nonFeatsFields = nonFeatsFields.concat(Entity.nonFeaturesFields());
      }
      //TODO: custom fields from other types
      for (const feat in sch.fields) {
        if (!nonFeatsFields.includes(feat)) {
          if (["int", "float", "str", "bool"].includes(sch.fields[feat].type)) {
            featuresArray.push({
              name: feat,
              required: false, //TODO (info not in datasetSchema (nowhere yet))
              label: `[${tname}] ${feat}`,
              type: sch.fields[feat].type as "int" | "float" | "str" | "bool",
              sch: { name: tname, group, base_schema: sch.base_schema },
            });
          }
          if ("list" === sch.fields[feat].type) {
            featuresArray.push({
              name: feat,
              required: false, //TODO (info not in datasetSchema (nowhere yet))
              label: feat,
              type: "list",
              options: [], //TODO for list type (not covered yet)
              sch: { name: tname, group, base_schema: sch.base_schema },
            });
          }
        }
      }
    }
  });
  return { inputs: featuresArray };
};

export const getEntityProperties = (
  formInputs: CreateEntityInputs,
  initialValues: Record<string, Record<string, ItemFeature>>,
  objectProperties: EntityProperties,
) => {
  for (const feat of formInputs) {
    if (feat.sch.name in initialValues && feat.name in initialValues[feat.sch.name]) {
      if (typeof initialValues[feat.sch.name][feat.name].value !== "object") {
        if (!(feat.sch.name in objectProperties)) objectProperties[feat.sch.name] = {};
        if (!(feat.name in objectProperties[feat.sch.name])) {
          objectProperties[feat.sch.name][feat.name] = initialValues[feat.sch.name][feat.name]
            .value as string | number | boolean;
        }
      }
    } else {
      if (!(feat.sch.name in objectProperties)) objectProperties[feat.sch.name] = {};
      if (!(feat.name in objectProperties[feat.sch.name])) {
        if (feat.type === "bool") objectProperties[feat.sch.name][feat.name] = false;
        if (feat.type === "str") objectProperties[feat.sch.name][feat.name] = "";
        if (feat.type === "int" || feat.type === "float")
          objectProperties[feat.sch.name][feat.name] = 0;
        if (feat.type === "list") objectProperties[feat.sch.name][feat.name] = ""; //TODO list case... ??
      }
    }
  }
  return objectProperties;
};
