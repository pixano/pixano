import { createObjectInputsSchema } from "../../lib/settings/objectValidationSchemas";
import type {
  DatasetItem,
  FeatureValues,
  ItemFeature,
  FeaturesValues,
} from "@pixano/core";
import type {
  CheckboxFeature,
  CreateObjectInputs,
  Feature,
  ListFeature,
  IntFeature,
  FloatFeature,
  TextFeature,
} from "../../lib/types/imageWorkspaceTypes";

export const createFeature = (features: DatasetItem["features"]): Feature[] => {
  const parsedFeatures = createObjectInputsSchema.parse(
    Object.values(features).map((feature) => ({
      ...feature,
      type: feature.dtype as Feature["type"],
      required: false,
      label: feature.name,
    })),
  );
  return parsedFeatures.map((feature) => {
    const value = features[feature.name]?.value;
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
  store: FeaturesValues,
  feature_class: string,
  feature: string,
  value: string,
) => {
  // add new inputs to lists of available values
  if (feature_class === "objects" || feature_class === "scene") {
    if (!store[feature_class][feature]) {
      store[feature_class][feature] = [value];
    } else if (!store[feature_class][feature].includes(value)) {
      store[feature_class][feature].push(value);
    }
  }
};
