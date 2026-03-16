/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { toDatasetBrowser } from "./adapters";
import { buildQueryString, requestJson } from "./apiClient";
import type { PaginatedResponse, RecordResponse } from "./restTypes";
import type { DatasetBrowser } from "$lib/types/dataset";

interface ListRecordsOptions {
  limit?: number;
  offset?: number;
  where?: string;
  sort?: { col: string; order: string };
  workspaceType?: string;
}

export async function listRecords(
  datasetId: string,
  options: ListRecordsOptions = {},
): Promise<DatasetBrowser> {
  const query = buildQueryString({
    limit: options.limit ?? 100,
    offset: options.offset ?? 0,
    where: options.where,
    include: "view_previews",
  });
  const records = await requestJson<PaginatedResponse<RecordResponse>>(
    `/datasets/${datasetId}/records${query}`,
    {},
    "listRecords",
  );
  return toDatasetBrowser(datasetId, records, options.sort);
}

export async function getRecord(datasetId: string, recordId: string): Promise<RecordResponse> {
  return await requestJson<RecordResponse>(
    `/datasets/${datasetId}/records/${recordId}`,
    {},
    "getRecord",
  );
}

export async function listAllRecordIds(datasetId: string): Promise<string[]> {
  const ids: string[] = [];
  let offset = 0;
  const limit = 1000;

  while (true) {
    const query = buildQueryString({ limit, offset });
    const page = await requestJson<PaginatedResponse<RecordResponse>>(
      `/datasets/${datasetId}/records${query}`,
      {},
      "listAllRecordIds",
    );

    ids.push(...page.items.map((record) => record.id));

    if (ids.length >= page.total || page.items.length === 0) {
      return ids;
    }

    offset += page.limit;
  }
}
