/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import { BaseSchema, type BBox, type Entity, type Source } from "@pixano/core";

import { sourcesStore } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { DEFAULT_FEATURES } from "../../settings/defaultFeatures";

export const defineTooltip = (bbox: BBox, entity: Entity): string | null => {
  if (!(bbox && bbox.is_type(BaseSchema.BBox))) return null;

  const source = get<Source[]>(sourcesStore).find((src) => src.id === bbox.data.source_ref.id);

  const confidence =
    bbox.data.confidence !== 0.0 &&
    source &&
    source.data.kind !== "ground_truth" &&
    source.data.name !== "Pixano"
      ? " " + bbox.data.confidence.toFixed(2)
      : "";

  for (const default_feature of DEFAULT_FEATURES) {
    if (default_feature in entity.data) {
      return typeof entity.data[default_feature] === "string"
        ? entity.data[default_feature] + confidence
        : null;
    }
  }
  return null;
};
