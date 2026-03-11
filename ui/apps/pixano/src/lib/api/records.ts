import { toDatasetBrowser } from "./adapters";
import { ApiError, buildQueryString, requestJson } from "./apiClient";
import type { ImageResponse, PaginatedResponse, RecordResponse, SFrameResponse } from "./restTypes";
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
  });
  const records = await requestJson<PaginatedResponse<RecordResponse>>(
    `/datasets/${datasetId}/records${query}`,
    {},
    "listRecords",
  );
  const viewsByRecordId = await listViewsForRecords(
    datasetId,
    records.items.map((record) => record.id),
    options.workspaceType,
  );
  return toDatasetBrowser(datasetId, records, options.sort, viewsByRecordId);
}

async function requestViewPage<T>(url: string, label: string): Promise<PaginatedResponse<T>> {
  try {
    return await requestJson<PaginatedResponse<T>>(url, {}, label);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return { items: [], total: 0, limit: 0, offset: 0 };
    }
    throw error;
  }
}

async function listViewsForRecords(
  datasetId: string,
  recordIds: string[],
  workspaceType?: string,
): Promise<Record<string, Array<ImageResponse | SFrameResponse>>> {
  const shouldLoadSFrames = workspaceType === "video";

  const entries = await Promise.all(
    recordIds.map(async (recordId) => {
      const query = buildQueryString({ limit: 1000, offset: 0 });
      const page = shouldLoadSFrames
        ? await requestViewPage<SFrameResponse>(
            `/datasets/${datasetId}/records/${recordId}/sframes${query}`,
            "listRecordSFrames",
          )
        : await requestViewPage<ImageResponse>(
            `/datasets/${datasetId}/records/${recordId}/images${query}`,
            "listRecordImages",
          );

      return [recordId, page.items] as const;
    }),
  );

  return Object.fromEntries(entries);
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
