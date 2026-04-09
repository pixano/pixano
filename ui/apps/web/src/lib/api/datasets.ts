/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { toDataset, toDatasetInfo } from "./adapters";
import { apiFetch, requestJson } from "./apiClient";
import type { DatasetInfoResponse, DatasetResponse } from "./restTypes";
import type { Dataset, DatasetInfo } from "$lib/types/dataset";

export async function listDatasets(): Promise<DatasetInfo[]> {
  const datasets = await apiFetch<DatasetInfoResponse[]>("/datasets", {}, [], "listDatasets");
  return datasets.map(toDatasetInfo);
}

export async function getDataset(datasetId: string): Promise<Dataset> {
  const dataset = await requestJson<DatasetResponse>(`/datasets/${datasetId}`, {}, "getDataset");
  return toDataset(dataset);
}
