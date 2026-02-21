/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  DatasetBrowser,
  DatasetInfo,
  DatasetItem,
  type Dataset,
  type DatasetBrowserType,
  type DatasetInfoType,
  type DatasetItemType,
  type DatasetMoreInfo,
  type Source,
  type ViewEmbedding,
} from "$lib/types/dataset";
import * as utils from "$lib/utils/coreUtils";

import { apiFetch } from "./apiClient";

// ─── getBrowser ─────────────────────────────────────────────────────────────────

interface BrowserSort {
  col: string;
  order: string;
}

let currentAbortController: AbortController | null = null;

function isAbortLikeError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === "AbortError") {
    return true;
  }
  return typeof error === "string" && error === "aborted";
}

function getBrowserQueryParams(
  page: number,
  size: number,
  query: Record<string, string> | undefined,
  where: string | undefined,
  sort: BrowserSort | undefined,
): string {
  let queryParams = `skip=${(page - 1) * size}&limit=${size}`;

  if (query && query.model !== "" && query.search !== "") {
    queryParams += `&query=${encodeURIComponent(query.search)}&embedding_table=${query.model}`;
  }

  if (where && where !== "") {
    queryParams += `&where=${encodeURIComponent(where)}`;
  }

  if (sort && sort.col !== "" && (sort.order === "asc" || sort.order === "desc")) {
    queryParams += `&sortcol=${encodeURIComponent(sort.col)}&order=${sort.order}`;
  }

  return queryParams;
}

export async function getBrowser(
  datasetId: string,
  page: number = 1,
  size: number = 100,
  query: Record<string, string> | undefined,
  where: string | undefined,
  sort: BrowserSort | undefined,
): Promise<DatasetBrowser> {
  // Cancel any previous in-flight request
  if (currentAbortController) {
    currentAbortController.abort();
  }
  currentAbortController = new AbortController();
  const signal = currentAbortController.signal;
  const queryParams = getBrowserQueryParams(page, size, query, where, sort);

  try {
    const response = await fetch(`/browser/${datasetId}?${queryParams}`, { signal });
    if (response.ok) {
      const raw = (await response.json()) as DatasetBrowserType;
      return new DatasetBrowser(raw);
    }
    console.error("api.getBrowser -", response.status, response.statusText, await response.text());
  } catch (e) {
    if (isAbortLikeError(e)) {
      return {} as DatasetBrowser;
    }
    console.error("api.getBrowser -", e);
  }
  return {} as DatasetBrowser;
}

// ─── getDataset ─────────────────────────────────────────────────────────────────

export function getDataset(datasetId: string): Promise<Dataset> {
  return apiFetch(`/datasets/${datasetId}`, {}, {} as Dataset, "getDataset");
}

// ─── getDatasetItem ─────────────────────────────────────────────────────────────

export function getDatasetItem(datasetId: string, itemId: string): Promise<DatasetItem> {
  return apiFetch(
    `/dataset_items/${datasetId}/${itemId}`,
    {},
    {} as DatasetItem,
    "getDatasetItem",
    (json) => new DatasetItem(json as DatasetItemType),
  );
}

// ─── getDatasetItemsIds ─────────────────────────────────────────────────────────

export async function getDatasetItemsIds(datasetId: string): Promise<Array<string>> {
  try {
    const response = await fetch(`/browser/item_ids/${datasetId}`);
    if (response.ok) {
      return (await response.json()) as string[];
    }
    if (response.status !== 404) {
      console.error(
        "api.getDatasetItemsIds -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.error("api.getDatasetItemsIds -", e);
  }
  return [];
}

// ─── getDatasetStats ────────────────────────────────────────────────────────────

export type DatasetStats = Record<string, Record<string, number>>;

export async function getDatasetStats(
  datasetId: string,
  options?: { signal?: AbortSignal },
): Promise<DatasetStats> {
  try {
    const response = await fetch(`/datasets/${datasetId}/stats`, {
      method: "GET",
      signal: options?.signal,
    });
    if (response.ok) {
      return (await response.json()) as DatasetStats;
    }
    console.error(
      "api.getDatasetStats -",
      response.status,
      response.statusText,
      await response.text(),
    );
  } catch (e) {
    if (!isAbortLikeError(e)) {
      console.error("api.getDatasetStats -", e);
    }
  }
  return {};
}

// ─── getDatasetsInfo ────────────────────────────────────────────────────────────

export function getDatasetsInfo(): Promise<Array<DatasetInfo>> {
  return apiFetch(
    "/datasets/info",
    {},
    [] as DatasetInfo[],
    "getDatasetsInfo",
    (json) => (json as DatasetInfoType[]).map((raw) => new DatasetInfo(raw)),
  );
}

// ─── getItemsInfo ───────────────────────────────────────────────────────────────

export async function getItemsInfo(
  datasetId: string,
  itemIds: string[] | null = null,
  options?: { signal?: AbortSignal },
): Promise<Array<DatasetMoreInfo>> {
  let url: string;
  if (itemIds && itemIds.length > 0) {
    const idsChunks = utils.splitWithLimit(itemIds, "&ids=", 8000);
    url = `/items_info/${datasetId}?ids=${idsChunks[0]}`;
  } else {
    url = `/items_info/${datasetId}`;
  }

  try {
    const response = await fetch(url, {
      method: "GET",
      signal: options?.signal,
    });
    if (response.ok) {
      return (await response.json()) as Array<DatasetMoreInfo>;
    }
    console.error(
      "api.getItemsInfo -",
      response.status,
      response.statusText,
      await response.text(),
    );
  } catch (e) {
    if (!isAbortLikeError(e)) {
      console.error("api.getItemsInfo -", e);
    }
  }
  return [];
}

// ─── getSources ─────────────────────────────────────────────────────────────────

export async function getSources(datasetId: string): Promise<Source[]> {
  const response = await fetch(`/sources/${datasetId}`);
  if (response.ok) {
    return (await response.json()) as Source[];
  }
  if (response.status !== 404) {
    console.error("api.getSources -", response.status, response.statusText, await response.text());
  }
  return [];
}

// ─── getViewEmbeddings ──────────────────────────────────────────────────────────

export function getViewEmbeddings(
  datasetId: string,
  itemId: string,
  tableName: string,
  where: string,
): Promise<Array<ViewEmbedding>> {
  let whereQuery = "";
  if (where !== "") {
    whereQuery = `&where=${where}`;
  }
  return apiFetch(
    `/embeddings/${datasetId}/${tableName}?item_ids=${itemId}${whereQuery}`,
    {},
    [] as ViewEmbedding[],
    "getViewEmbeddings",
  );
}
