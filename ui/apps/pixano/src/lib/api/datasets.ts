/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { toDataset, toDatasetInfo } from "./adapters";
import { apiFetch, JSON_HEADERS, requestJson } from "./apiClient";
import type { DatasetInfoResponse, DatasetResponse } from "./restTypes";
import type { Dataset, DatasetInfo } from "$lib/types/dataset";

export interface ImportJobStatus {
  job_id: string;
  status: "pending" | "running" | "done" | "error";
  message: string;
  dataset_id: string;
}

export async function listDatasets(): Promise<DatasetInfo[]> {
  const datasets = await apiFetch<DatasetInfoResponse[]>("/datasets", {}, [], "listDatasets");
  return datasets.map(toDatasetInfo);
}

export async function getDataset(datasetId: string): Promise<Dataset> {
  const dataset = await requestJson<DatasetResponse>(`/datasets/${datasetId}`, {}, "getDataset");
  return toDataset(dataset);
}

export async function startDatasetImport(
  sourceDir: string,
  importType: string,
  datasetName: string,
): Promise<ImportJobStatus> {
  return requestJson<ImportJobStatus>(
    "/datasets/import",
    {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({
        source_dir: sourceDir,
        import_type: importType,
        dataset_name: datasetName,
      }),
    },
    "startDatasetImport",
  );
}

export async function getImportJob(jobId: string): Promise<ImportJobStatus> {
  return requestJson<ImportJobStatus>(`/datasets/import/${jobId}`, {}, "getImportJob");
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
