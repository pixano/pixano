import { createObjectInputsSchema } from "../../lib/settings/objectValidationSchemas";
import type { DatasetItem, FeatureValues, ItemFeature } from "@pixano/core";
import type {
  CheckboxFeature,
  CreateObjectInputs,
  Feature,
  ListFeature,
  NumberFeature,
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
    return { ...feature, value } as NumberFeature | TextFeature | CheckboxFeature;
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
