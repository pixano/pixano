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
  const baseRoute = `/explorer/${datasetId}`;
  if (!query) return baseRoute;
  return query.startsWith("?") ? `${baseRoute}${query}` : `${baseRoute}?${query}`;
};

export const getWorkspaceRoute = (datasetId: string, itemId: string): string =>
  `/explorer/${datasetId}/workspace/${itemId}`;

export const findNeighborItemId = (
  itemsIds: string[],
  direction: "previous" | "next",
  currentItemId: string,
): string | undefined => {
  const currentIndex: number = itemsIds.findIndex((item) => item === currentItemId);
  if (currentIndex === -1) return undefined;

  const nextIndex = direction === "previous" ? currentIndex - 1 : currentIndex + 1;
  if (nextIndex === -1) return itemsIds[itemsIds.length - 1];
  if (nextIndex === itemsIds.length) return itemsIds[0];
  return itemsIds[nextIndex];
};

export const getPageFromItemId = (itemsIds: string[], currentItemId: string): number => {
  const currentIndex: number = itemsIds.findIndex((item) => item === currentItemId);
  return Math.floor(currentIndex / DEFAULT_DATASET_TABLE_SIZE) + 1;
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
