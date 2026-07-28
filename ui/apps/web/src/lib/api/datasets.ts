/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { toDataset, toDatasetInfo } from "./adapters";
import { apiFetch, requestJson } from "./apiClient";
import type {
  DatasetInfoResponse,
  DatasetResponse,
  PaginatedResponse,
  RecordResponse,
} from "./restTypes";
import type { Dataset, DatasetInfo } from "$lib/types/dataset";

export async function listDatasets(): Promise<DatasetInfo[]> {
  const datasets = await apiFetch<DatasetInfoResponse[]>("/datasets", {}, [], "listDatasets");
  return datasets.map(toDatasetInfo);
}

export async function getDataset(datasetId: string): Promise<Dataset> {
  const dataset = await requestJson<DatasetResponse>(`/datasets/${datasetId}`, {}, "getDataset");
  return toDataset(dataset);
}

export async function listRecords(
  datasetId: string,
  limit = 50,
  offset = 0,
): Promise<PaginatedResponse<RecordResponse>> {
  return requestJson<PaginatedResponse<RecordResponse>>(
    // `include=view_previews` asks the backend to attach each record's per-view
    // thumbnail descriptors so the left panel can render image previews.
    `/datasets/${datasetId}/records?limit=${limit}&offset=${offset}&include=view_previews`,
    {},
    "listRecords",
  );
}
