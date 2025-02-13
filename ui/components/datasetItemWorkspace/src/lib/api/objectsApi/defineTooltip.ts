/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import { BaseSchema, type BBox, type Entity, type Source } from "@pixano/core";

import { sourcesStore } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { DEFAULT_FEATURE } from "../../settings/defaultFeatures";

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

  const tooltip =
    typeof entity.data[DEFAULT_FEATURE] === "string"
      ? entity.data[DEFAULT_FEATURE] + confidence
      : null;
  return tooltip;
};
