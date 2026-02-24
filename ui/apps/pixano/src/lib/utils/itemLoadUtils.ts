/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  WorkspaceType,
  type DatasetInfo,
  type DatasetItem,
  type DatasetSchema,
  type FeaturesValues,
  type Image,
  type SequenceFrame,
} from "$lib/types/dataset";

type BackFeatureValue = {
  name: string;
  restricted: boolean;
  values: string[];
};
type BackFeatureValues = Record<string, Record<string, BackFeatureValue[]>>;
const ABSOLUTE_URL_RE = /^(?:[a-z][a-z0-9+.-]*:)?\/\//i;
const INLINE_URL_RE = /^(?:blob:|data:)/i;

function normalizeImageUrl(url: string): string {
  const trimmed = url.trim();
  if (!trimmed) return trimmed;

  if (ABSOLUTE_URL_RE.test(trimmed) || INLINE_URL_RE.test(trimmed)) {
    return trimmed;
  }

  const normalized = trimmed.replace(/^\/+/, "");
  if (normalized.startsWith("views/") || normalized.startsWith("media/")) {
    return normalized;
  }

  return `media/${normalized}`;
}

export function isValidDatasetItem(value: unknown): value is DatasetItem {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<DatasetItem>;
  return (
    typeof candidate.item?.id === "string" &&
    candidate.item.id.length > 0 &&
    typeof candidate.views === "object" &&
    candidate.views !== null &&
    typeof candidate.entities === "object" &&
    candidate.entities !== null &&
    typeof candidate.annotations === "object" &&
    candidate.annotations !== null
  );
}

export function prepareDatasetItem(
  rawItem: DatasetItem,
  dataset: DatasetInfo,
): DatasetItem {
  const item = rawItem;

  // Infer workspace type if not defined
  if (dataset.workspace === WorkspaceType.UNDEFINED) {
    for (const viewname in item.views) {
      if (Array.isArray(item.views[viewname])) {
        dataset.workspace = WorkspaceType.VIDEO;
        break;
      } else {
        const is_vqa = "conversations" in item.entities;
        if (is_vqa) {
          dataset.workspace = WorkspaceType.IMAGE_VQA;
          break;
        } else {
          dataset.workspace = WorkspaceType.IMAGE;
        }
      }
    }
  }

  // Normalize media URLs and set image/sequence frame UI type.
  if (dataset.workspace === WorkspaceType.VIDEO) {
    for (const viewname in item.views) {
      const view = item.views[viewname];
      if (Array.isArray(view)) {
        const video = view as SequenceFrame[];
        video.forEach((sf) => {
          sf.data.type = WorkspaceType.VIDEO;
        });
        video.sort((a, b) => a.data.frame_index - b.data.frame_index);
      } else {
        throw Error("Video workspace without SequenceFrames.");
      }
    }
  } else {
    for (const viewname in item.views) {
      const view = item.views[viewname];
      if (Array.isArray(view)) {
        throw Error("Not video workspace with SequenceFrames.");
      } else {
        const image = view as Image;
        image.data.type = WorkspaceType.IMAGE;
        image.data.url = normalizeImageUrl(image.data.url);
      }
    }
  }

  item.ui = { type: dataset.workspace, datasetId: dataset.id };
  return item;
}

export function mapFeatureValues(
  rawFeatureValues: object,
  schema: DatasetSchema,
): FeaturesValues {
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
