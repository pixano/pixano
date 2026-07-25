/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { toDatasetBrowser } from "./adapters";
import { JSON_HEADERS, requestJson } from "./apiClient";
import type { PaginatedResponse, RecordResponse } from "./restTypes";
import type { DatasetBrowser } from "$lib/types/dataset";

export interface RecordSearchOptions {
  model?: string;
  text?: string;
  similarTo?: string;
  k?: number;
  filters?: string[];
  where?: string;
}

interface RecordSearchResponse {
  items: RecordResponse[];
  total: number;
  model: string;
  mode: string;
  k: number;
}

/** Semantic search over records (text→records or find-similar); returns a ranked browser view. */
export async function searchRecords(
  datasetId: string,
  options: RecordSearchOptions,
): Promise<DatasetBrowser> {
  const k = options.k ?? 50;
  const response = await requestJson<RecordSearchResponse>(
    `/datasets/${datasetId}/records/search`,
    {
      headers: JSON_HEADERS,
      method: "POST",
      body: JSON.stringify({
        model: options.model,
        text: options.text,
        similar_to: options.similarTo,
        k,
        filter: options.filters,
        where: options.where,
      }),
    },
    "searchRecords",
  );
  // The ranked items already carry `_distance` + `view_previews`; render them like a page.
  const paginated: PaginatedResponse<RecordResponse> = {
    items: response.items,
    total: response.total,
    limit: k,
    offset: 0,
  };
  return toDatasetBrowser(datasetId, paginated);
}

/** Launch the record-embedding computation job; returns the job id (poll via getIoJob). */
export async function computeEmbeddings(datasetId: string, model: string): Promise<string> {
  const response = await requestJson<{ job_id: string }>(
    `/datasets/${datasetId}/embeddings/compute`,
    { headers: JSON_HEADERS, method: "POST", body: JSON.stringify({ model }) },
    "computeEmbeddings",
  );
  return response.job_id;
}
