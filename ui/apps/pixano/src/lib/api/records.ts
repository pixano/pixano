/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { toDatasetBrowser } from "./adapters";
import { buildQueryString, JSON_HEADERS, requestJson } from "./apiClient";
import type { PaginatedResponse, RecordResponse } from "./restTypes";
import type { DatasetBrowser } from "$lib/types/dataset";

/** Record annotation-workflow states, in progression order. */
export const RECORD_STATUSES = ["new", "inProgress", "inReview", "validated"] as const;
export type RecordStatus = (typeof RECORD_STATUSES)[number];

export const RECORD_STATUS_LABELS: Record<RecordStatus, string> = {
  new: "New",
  inProgress: "In progress",
  inReview: "In review",
  validated: "Validated",
};

export interface ListRecordsOptions {
  limit?: number;
  offset?: number;
  /** Serialized `col:op:value` filter tokens (repeated `filter=` params). */
  filters?: string[];
  /** Free-text search over searchable string columns. */
  q?: string;
  /** Deprecated raw SQL where clause. */
  where?: string;
  sort?: string;
  order?: string;
}

export async function listRecords(
  datasetId: string,
  options: ListRecordsOptions = {},
): Promise<DatasetBrowser> {
  const query = buildQueryString({
    limit: options.limit ?? 100,
    offset: options.offset ?? 0,
    filter: options.filters,
    q: options.q,
    where: options.where,
    sort: options.sort,
    order: options.order,
    include: "view_previews",
  });
  const records = await requestJson<PaginatedResponse<RecordResponse>>(
    `/datasets/${datasetId}/records${query}`,
    {},
    "listRecords",
  );
  return toDatasetBrowser(datasetId, records);
}

export async function getRecord(datasetId: string, recordId: string): Promise<RecordResponse> {
  return await requestJson<RecordResponse>(
    `/datasets/${datasetId}/records/${recordId}`,
    {},
    "getRecord",
  );
}

/** Update a record's annotation-workflow status. */
export async function updateRecordStatus(
  datasetId: string,
  recordId: string,
  status: RecordStatus,
): Promise<RecordResponse> {
  return await requestJson<RecordResponse>(
    `/datasets/${datasetId}/records/${recordId}`,
    { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify({ status }) },
    "updateRecordStatus",
  );
}
