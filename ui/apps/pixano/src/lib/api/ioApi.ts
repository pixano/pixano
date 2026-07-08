/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { JSON_HEADERS, requestJson } from "./apiClient";
import type {
  FolderBrowseResponse,
  ImportPlanResponse,
  IoFormatResponse,
  IoJobResponse,
} from "./restTypes";

/** List the registered data formats (import wizard format picker). */
export async function listIoFormats(): Promise<IoFormatResponse[]> {
  return requestJson<IoFormatResponse[]>("/io/formats", {}, "listIoFormats");
}

/** List a server directory's subfolders (source picker); empty path = server home. */
export async function browseServerFolders(path = ""): Promise<FolderBrowseResponse> {
  const query = path ? `?path=${encodeURIComponent(path)}` : "";
  return requestJson<FolderBrowseResponse>(`/io/browse${query}`, {}, "browseServerFolders");
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

/** Queue an import job (202) from a saved plan_id and/or a spec+source pair. */
export async function startIoImport(request: {
  plan_id?: string;
  source: string;
  spec?: Record<string, unknown>;
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
      }),
    },
    "startIoImport",
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
