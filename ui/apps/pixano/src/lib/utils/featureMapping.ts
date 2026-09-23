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
  MultiPath,
  TextSpan,
  Tracklet,
  type FeatureList,
  type FeaturesValues,
  type FieldInfo,
  type ItemFeature,
} from "$lib/types/dataset";
import type { FeatureValues } from "$lib/types/shapeTypes";
import type { CreateEntityInputs, EntityProperties, Feature } from "$lib/types/workspace";
import type {
  InputFeatures,
  ScalarFeatureType,
  TableInfo,
} from "$lib/utils/featureValidationSchemas";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

function fieldInput(name: string, field: FieldInfo, sch: TableInfo): InputFeatures[number] | null {
  const common = {
    name,
    label: name,
    required: field.required ?? false,
    default: field.default,
    sch,
  };
  if (["int", "float", "str", "bool"].includes(field.type)) {
    const type = field.type as ScalarFeatureType;
    return field.collection
      ? { ...common, type: "collection", itemType: type }
      : { ...common, type };
  }
  return field.type === "list" ? { ...common, type: "list", options: [] } : null;
}

export function createFeature(
  obj: Item | Entity | Annotation,
  workspaceManifest: WorkspaceManifest,
  additional_info: string = "",
): Feature[] {
  const prefix = additional_info !== "" ? "[" + additional_info + "] " : "";
  return obj.getDynamicFields().flatMap((name) => {
    const field = workspaceManifest.tablesByName[obj.table_info.name]?.fields[name] ?? {
      type: "str",
      collection: false,
    };
    const input = fieldInput(name, field, {
      name: obj.table_info.name,
      group: obj.table_info.group,
      base_schema: obj.table_info.base_schema,
    });
    if (!input) return [];
    return [{ ...input, label: `${prefix}${name}`, value: obj.data[name], obj } as Feature];
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
          dtype: formInputs.find((o) => o.name === key && o.sch.name === tname)?.type ?? "str",
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
  return [...(featureList.values ?? [])]
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
        if (baseSchema === BaseSchema.MultiPath)
          nonFeatsFields = nonFeatsFields.concat(MultiPath.nonFeaturesFields());
      } else {
        nonFeatsFields = nonFeatsFields.concat(Entity.nonFeaturesFields());
      }
      //TODO: custom fields from other types
      for (const feat in sch.fields) {
        if (!nonFeatsFields.includes(feat)) {
          const input = fieldInput(feat, sch.fields[feat], {
            name: tname,
            group,
            base_schema: sch.base_schema,
          });
          if (input) featuresArray.push(input);
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
    if (!(feat.sch.name in objectProperties)) objectProperties[feat.sch.name] = {};
    if (feat.name in objectProperties[feat.sch.name]) continue;
    if (feat.sch.name in initialValues && feat.name in initialValues[feat.sch.name]) {
      const value = initialValues[feat.sch.name][feat.name].value;
      if (typeof value !== "object" || Array.isArray(value)) {
        objectProperties[feat.sch.name][feat.name] = Array.isArray(value) ? [...value] : value;
      }
    } else if (feat.default !== undefined) {
      objectProperties[feat.sch.name][feat.name] = (
        Array.isArray(feat.default)
          ? [...(feat.default as Array<string | number | boolean>)]
          : feat.default
      ) as FeatureValues;
    } else {
      if (feat.type === "collection") objectProperties[feat.sch.name][feat.name] = [];
      if (feat.type === "bool") objectProperties[feat.sch.name][feat.name] = false;
      if (feat.type === "str" || feat.type === "list")
        objectProperties[feat.sch.name][feat.name] = "";
      if (!feat.required && (feat.type === "int" || feat.type === "float")) {
        objectProperties[feat.sch.name][feat.name] = 0;
      }
    }
  }
  return objectProperties;
};
