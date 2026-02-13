/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { DatasetBrowser, type DatasetBrowserType } from "../lib/types";

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

  let datasetItems: DatasetBrowser;
  let datasetItems_raw: DatasetBrowserType;

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
      datasetItems_raw = (await response.json()) as DatasetBrowserType;
      datasetItems = new DatasetBrowser(datasetItems_raw);
    } else {
      datasetItems = {} as DatasetBrowser;
      console.log("api.getBrowser -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      // Request was cancelled by a newer request — return empty
      return {} as DatasetBrowser;
    }
    datasetItems = {} as DatasetBrowser;
    console.log("api.getBrowser -", e);
  }

  return datasetItems;
}
