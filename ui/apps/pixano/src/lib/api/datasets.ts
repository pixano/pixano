/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { toDataset, toDatasetInfo } from "./adapters";
import { requestJson } from "./apiClient";
import type { DatasetInfoResponse, DatasetResponse } from "./restTypes";
import type { Dataset, DatasetInfo } from "$lib/types/dataset";

export async function listDatasets(): Promise<DatasetInfo[]> {
  const datasets = await requestJson<DatasetInfoResponse[]>("/datasets", {}, "listDatasets");
  return datasets.map(toDatasetInfo);
}

export async function getDataset(datasetId: string): Promise<Dataset> {
  const dataset = await requestJson<DatasetResponse>(`/datasets/${datasetId}`, {}, "getDataset");
  return toDataset(dataset);
}

export async function getDatasetStats(
  datasetId: string,
  options?: { signal?: AbortSignal },
): Promise<Record<string, Record<string, number>>> {
  return await requestJson<Record<string, Record<string, number>>>(
    `/datasets/${datasetId}/stats`,
    { method: "GET", signal: options?.signal },
    "getDatasetStats",
  );
}
