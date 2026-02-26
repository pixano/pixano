/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { PageLoad } from "./$types";
import * as api from "$lib/api";
import { error } from "@sveltejs/kit";
import {
  isValidDatasetItem,
  prepareDatasetItem,
  mapFeatureValues,
} from "$lib/utils/itemLoadUtils";

export const load: PageLoad = async ({ params, parent }) => {
  const { dataset, schema, featureValues: rawFeatureValues } = await parent();

  const rawItem = await api.getDatasetItem(dataset.id, encodeURIComponent(params.itemId));
  if (!isValidDatasetItem(rawItem)) {
    // eslint-disable-next-line @typescript-eslint/only-throw-error
    throw error(404, `Item "${params.itemId}" not found`);
  }

  const item = prepareDatasetItem(rawItem, dataset);
  const featureValues = mapFeatureValues(rawFeatureValues, schema);

  return { item, featureValues };
};
