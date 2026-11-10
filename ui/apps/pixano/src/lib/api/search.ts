/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { toDatasetBrowser } from "./adapters";
import { JSON_HEADERS, requestJson } from "./apiClient";
import type { EmbeddingSpaceStatusResponse, PaginatedResponse, RecordResponse } from "./restTypes";
import type { DatasetBrowser } from "$lib/types/dataset";

export interface RecordSearchOptions {
  /** The model's embeddings to search: a model's id, or its name; the default model's when absent. */
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

/**
 * Launch the record-embedding computation job; returns the job id (poll via getIoJob).
 *
 * The model's embeddings go beside the other models'. `force` empties that model's embeddings
 * first — to compute them again from nothing, or to repair them —, or deletes every model's when
 * the dataset's description of them cannot be read entirely. `provider` names the inference to
 * compute them on; the server's default one when absent.
 */
export async function computeEmbeddings(
  datasetId: string,
  model: string,
  force = false,
  provider?: string,
): Promise<string> {
  const response = await requestJson<{ job_id: string }>(
    `/datasets/${datasetId}/embeddings/compute`,
    {
      headers: JSON_HEADERS,
      method: "POST",
      body: JSON.stringify({ model, force, provider_name: provider }),
    },
    "computeEmbeddings",
  );
  return response.job_id;
}

/** Make one of the dataset's embeddings models, by its id, the one a search naming no model reads. */
export async function setDefaultEmbeddingSpace(
  datasetId: string,
  spaceId: string,
): Promise<EmbeddingSpaceStatusResponse> {
  return requestJson<EmbeddingSpaceStatusResponse>(
    `/datasets/${datasetId}/embedding-spaces/default`,
    { headers: JSON_HEADERS, method: "PUT", body: JSON.stringify({ space_id: spaceId }) },
    "setDefaultEmbeddingSpace",
  );
}
