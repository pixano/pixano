/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { error } from "@sveltejs/kit";

import type { LayoutLoad } from "./$types";
import * as api from "$lib/api";

export const load: LayoutLoad = async ({ params, parent }) => {
  const { datasets } = await parent();
  const dataset = datasets.find((d) => d.id === params.datasetId);
  // eslint-disable-next-line @typescript-eslint/only-throw-error
  if (!dataset) throw error(404, `Dataset "${params.datasetId}" not found`);

  const [ds, itemIds] = await Promise.all([
    api.getDataset(params.datasetId),
    api.listAllRecordIds(params.datasetId),
  ]);

  return {
    dataset,
    schema: ds.schema,
    featureValues: ds.featureValues,
    itemIds,
  };
};
