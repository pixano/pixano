/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { buildQueryString, requestJson } from "./apiClient";
import type { FilterSchemaResponse, NeighborsResponse } from "./restTypes";

/** Fetch the explorer filter/sort/search capability document for a dataset. */
export async function getFilterSchema(datasetId: string): Promise<FilterSchemaResponse> {
  return await requestJson<FilterSchemaResponse>(
    `/datasets/${datasetId}/filters`,
    {},
    "getFilterSchema",
  );
}

export interface NeighborsQuery {
  filters?: string[];
  q?: string;
  sort?: string;
  order?: string;
  where?: string;
}

/** Fetch a record's neighbors within the active filter + sort. */
export async function getNeighbors(
  datasetId: string,
  recordId: string,
  query: NeighborsQuery = {},
): Promise<NeighborsResponse> {
  const qs = buildQueryString({
    filter: query.filters,
    q: query.q,
    sort: query.sort,
    order: query.order,
    where: query.where,
  });
  return await requestJson<NeighborsResponse>(
    `/datasets/${datasetId}/records/${recordId}/neighbors${qs}`,
    {},
    "getNeighbors",
  );
}
