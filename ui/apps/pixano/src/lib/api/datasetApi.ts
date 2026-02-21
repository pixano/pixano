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

let currentAbortController: AbortController | null = null;

export async function getBrowser(
  datasetId: string,
  page: number = 1,
  size: number = 100,
  query: Record<string, string> | undefined,
  where: string | undefined,
  sort: { col: string; order: string } | undefined,
): Promise<DatasetBrowser> {
  // Cancel any previous in-flight request
  if (currentAbortController) {
    currentAbortController.abort();
  }
  currentAbortController = new AbortController();
  const signal = currentAbortController.signal;

  let query_qparams = "";
  if (query && query.model !== "" && query.search !== "") {
    query_qparams = `&query=${encodeURIComponent(query.search)}&embedding_table=${query.model}`;
  }
  let where_qparams = "";
  if (where && where !== "") {
    where_qparams = `&where=${encodeURIComponent(where)}`;
  }
  let sort_qparams = "";
  if (sort && sort.col !== "" && ["asc", "desc"].includes(sort.order)) {
    sort_qparams = `&sortcol=${encodeURIComponent(sort.col)}&order=${sort.order}`;
  }

  try {
    const response = await fetch(
      `/browser/${datasetId}?skip=${(page - 1) * size}&limit=${size}${query_qparams}${where_qparams}${sort_qparams}`,
      { signal },
    );
    if (response.ok) {
      const raw = (await response.json()) as DatasetBrowserType;
      return new DatasetBrowser(raw);
    }
    console.log("api.getBrowser -", response.status, response.statusText, await response.text());
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      return {} as DatasetBrowser;
    }
    console.log("api.getBrowser -", e);
  }
  return {} as DatasetBrowser;
}

// ─── getDataset ─────────────────────────────────────────────────────────────────

export function getDataset(datasetId: string): Promise<Dataset> {
  return apiFetch(`/datasets/${datasetId}`, {}, {} as Dataset, "getDataset");
}

// ─── getDatasetItem ─────────────────────────────────────────────────────────────

export async function getDatasetItem(datasetId: string, itemId: string): Promise<DatasetItem> {
  const start = Date.now();
  const item = await apiFetch(
    `/dataset_items/${datasetId}/${itemId}`,
    {},
    {} as DatasetItem,
    "getDatasetItem",
    (json) => new DatasetItem(json as DatasetItemType),
  );
  console.log("api.getDatasetItem - Done in", Date.now() - start);
  return item;
}

// ─── getDatasetItemsIds ─────────────────────────────────────────────────────────

export async function getDatasetItemsIds(datasetId: string): Promise<Array<string>> {
  try {
    const response = await fetch(`/browser/item_ids/${datasetId}`);
    if (response.ok) {
      return (await response.json()) as string[];
    }
    if (response.status != 404)
      console.log(
        "api.getDatasetItemsIds -",
        response.status,
        response.statusText,
        await response.text(),
      );
  } catch (e) {
    console.log("api.getDatasetItemsIds -", e);
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
    console.log(
      "api.getDatasetStats -",
      response.status,
      response.statusText,
      await response.text(),
    );
  } catch (e) {
    if (!(typeof e === "string" && e === "aborted")) console.log("api.getDatasetStats -", e);
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
  item_ids: string[] | null = null,
  options?: { signal?: AbortSignal },
): Promise<Array<DatasetMoreInfo>> {
  let url: string;
  if (item_ids && item_ids.length > 0) {
    const ids_chunks = utils.splitWithLimit(item_ids, "&ids=", 8000);
    url = `/items_info/${datasetId}?ids=${ids_chunks[0]}`;
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
    console.log(
      "api.getItemsInfo -",
      response.status,
      response.statusText,
      await response.text(),
    );
  } catch (e) {
    if (!(typeof e === "string" && e === "aborted")) console.log("api.getItemsInfo -", e);
  }
  return [];
}

// ─── getSources ─────────────────────────────────────────────────────────────────

export async function getSources(datasetId: string): Promise<Source[]> {
  const response = await fetch(`/sources/${datasetId}`);
  if (response.ok) {
    return (await response.json()) as Source[];
  } else {
    if (response.status != 404)
      console.log("api.getSources -", response.status, response.statusText, await response.text());
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
  let ifWhere = "";
  if (where !== "") ifWhere = `&where=${where}`;
  return apiFetch(
    `/embeddings/${datasetId}/${tableName}?item_ids=${itemId}${ifWhere}`,
    {},
    [] as ViewEmbedding[],
    "getViewEmbeddings",
  );
}
