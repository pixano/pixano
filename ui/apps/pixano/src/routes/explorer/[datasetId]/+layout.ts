/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { error } from "@sveltejs/kit";

import type { LayoutLoad } from "./$types";
import * as api from "$lib/api";
import { EXPLORER_COLUMNS_DEPENDENCY } from "$lib/utils/explorerData";

export const load: LayoutLoad = async ({ params, parent, depends }) => {
  depends(EXPLORER_COLUMNS_DEPENDENCY);
  const { datasets } = await parent();
  const dataset = datasets.find((d) => d.id === params.datasetId);
  // eslint-disable-next-line @typescript-eslint/only-throw-error
  if (!dataset) throw error(404, `Dataset "${params.datasetId}" not found`);

  const [ds, filterSchema, splitCounts] = await Promise.all([
    api.getDataset(params.datasetId),
    api.getFilterSchema(params.datasetId),
    // Split/status counts feed the toolbar facets; tolerate failure (facets just lose counts).
    api.getDatasetSplits(params.datasetId).catch(() => []),
  ]);
  return {
    dataset,
    schema: ds.schema,
    featureValues: ds.featureValues,
    filterSchema,
    splitCounts,
  };
};
