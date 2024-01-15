import { objectInputSchema } from "../../lib/settings/objectValidationSchemas";
import type { DatasetItem } from "@pixano/core";
import type {
  CheckboxFeature,
  Feature,
  ListFeature,
  NumberFeature,
  TextFeature,
} from "../../lib/types/imageWorkspaceTypes";

export const createFeature = (features: DatasetItem["features"]): Feature[] => {
  const parsedFeatures = objectInputSchema.parse(
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
