/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { LayoutLoad } from "./$types";
import * as api from "$lib/api";
import { error } from "@sveltejs/kit";

export const load: LayoutLoad = async ({ params, parent }) => {
  const { datasets } = await parent();
  const dataset = datasets.find((d) => d.id === params.dataset);
  // eslint-disable-next-line @typescript-eslint/only-throw-error
  if (!dataset) throw error(404, `Dataset "${params.dataset}" not found`);

  const [ds, sources, itemIds] = await Promise.all([
    api.getDataset(params.dataset),
    api.getSources(params.dataset),
    api.getDatasetItemsIds(params.dataset),
  ]);

  return {
    dataset,
    schema: ds.dataset_schema,
    featureValues: ds.feature_values,
    sources,
    itemIds,
  };
};
