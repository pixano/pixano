/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { JSON_HEADERS, requestJson } from "./apiClient";
import type {
  ImportEmbeddingsOffer,
  ImportPlanResponse,
  ImportStatisticsOffer,
  IoFormatResponse,
  IoJobResponse,
  UploadSessionResponse,
} from "./restTypes";

/** List the registered data formats (import wizard format picker). */
export async function listIoFormats(): Promise<IoFormatResponse[]> {
  return requestJson<IoFormatResponse[]>("/io/formats", {}, "listIoFormats");
}

/** Create a staging session for a client-side folder upload. */
export async function createUploadSession(): Promise<UploadSessionResponse> {
  return requestJson<UploadSessionResponse>(
    "/io/uploads",
    { method: "POST" },
    "createUploadSession",
  );
}

/** Discard a staged upload (wizard cancelled before importing). */
export async function deleteUploadSession(uploadId: string): Promise<void> {
  const response = await fetch(`/io/uploads/${uploadId}`, { method: "DELETE" });
  if (!response.ok && response.status !== 404) {
    throw new Error(`deleteUploadSession failed (${response.status}).`);
  }
}

/** Analyze a source without side effects; returns the plan (+ plan_id). */
export async function analyzeImportSource(
  source: string,
  spec: Record<string, unknown> = {},
): Promise<ImportPlanResponse> {
  return requestJson<ImportPlanResponse>(
    "/io/analyze",
    { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ source, spec }) },
    "analyzeImportSource",
  );
}

/**
 * Queue an import job (202) from a saved plan_id and/or a spec+source pair.
 *
 * `compute_embeddings` and `compute_statistics` left out follow the server's defaults, which only
 * apply where their jobs can run; `embeddings_model` left out is the server's.
 */
export async function startIoImport(request: {
  plan_id?: string;
  source: string;
  spec?: Record<string, unknown>;
  compute_embeddings?: boolean;
  embeddings_model?: string;
  compute_statistics?: boolean;
}): Promise<IoJobResponse> {
  return requestJson<IoJobResponse>(
    "/io/imports",
    {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({
        plan_id: request.plan_id ?? "",
        source: request.source,
        spec: request.spec ?? {},
        compute_embeddings: request.compute_embeddings,
        embeddings_model: request.embeddings_model,
        compute_statistics: request.compute_statistics,
      }),
    },
    "startIoImport",
  );
}

/** Whether an import can queue the embeddings job of what it imports, and with which models. */
export async function getImportEmbeddingsOffer(): Promise<ImportEmbeddingsOffer> {
  return requestJson<ImportEmbeddingsOffer>(
    "/io/imports/embeddings",
    {},
    "getImportEmbeddingsOffer",
  );
}

/** Whether an import can queue the statistics job of its default statistics, for the dataset's overview. */
export async function getImportStatisticsOffer(): Promise<ImportStatisticsOffer> {
  return requestJson<ImportStatisticsOffer>(
    "/io/imports/statistics",
    {},
    "getImportStatisticsOffer",
  );
}

/** Poll one job. */
export async function getIoJob(jobId: string): Promise<IoJobResponse> {
  return requestJson<IoJobResponse>(`/io/jobs/${jobId}`, {}, "getIoJob");
}

/** Request cooperative cancellation (observed at the next flush boundary). */
export async function cancelIoJob(jobId: string): Promise<IoJobResponse> {
  return requestJson<IoJobResponse>(`/io/jobs/${jobId}/cancel`, { method: "POST" }, "cancelIoJob");
}
