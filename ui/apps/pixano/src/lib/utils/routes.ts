/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { DEFAULT_DATASET_TABLE_SIZE } from "$lib/constants";

export const LIBRARY_ROUTE = "/";
export const EXPLORER_ROUTE_ID = "/explorer/[datasetId]";
export const WORKSPACE_ROUTE_ID = "/explorer/[datasetId]/workspace/[itemId]";

export const getExplorerRoute = (datasetId: string, query?: string): string => {
  const baseRoute = `#/explorer/${datasetId}`;
  if (!query) return baseRoute;
  return query.startsWith("?") ? `${baseRoute}${query}` : `${baseRoute}?${query}`;
};

export const getWorkspaceRoute = (datasetId: string, itemId: string, query?: string): string => {
  const baseRoute = `#/explorer/${datasetId}/workspace/${itemId}`;
  if (!query) return baseRoute;
  return query.startsWith("?") ? `${baseRoute}${query}` : `${baseRoute}?${query}`;
};

/**
 * Query-param keys that describe the explorer's active result set and its
 * presentation (filter, sort, search, page size). `page` is intentionally
 * excluded — an item's page is derived from its position within the filtered
 * set (`getPageFromPosition`), not carried around; `size` IS carried so that
 * derivation matches the explorer's pagination.
 */
export const EXPLORER_QUERY_KEYS = ["filter", "q", "sort", "order", "where", "size"] as const;

/** Keep only the result-set-defining params (filter/sort/search) from a set. */
export const pickExplorerQuery = (params: URLSearchParams): URLSearchParams => {
  const picked = new URLSearchParams();
  for (const key of EXPLORER_QUERY_KEYS) {
    for (const value of params.getAll(key)) {
      if (value !== "") picked.append(key, value);
    }
  }
  return picked;
};

/** 1-based page number for a 1-based position within the result set. */
export const getPageFromPosition = (
  position: number,
  pageSize: number = DEFAULT_DATASET_TABLE_SIZE,
): number => {
  return Math.floor((position - 1) / Math.max(pageSize, 1)) + 1;
};

export const getRouteSearchParams = (url: URL): URLSearchParams => {
  if (url.search) {
    return new URLSearchParams(url.search);
  }

  const hash = url.hash.startsWith("#") ? url.hash.slice(1) : url.hash;
  const queryIndex = hash.indexOf("?");
  if (queryIndex === -1) {
    return new URLSearchParams();
  }

  return new URLSearchParams(hash.slice(queryIndex + 1));
};
