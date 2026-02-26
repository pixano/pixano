/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const LIBRARY_ROUTE = "/";
export const EXPLORER_ROUTE_ID = "/explorer/[datasetId]";
export const WORKSPACE_ROUTE_ID = "/explorer/[datasetId]/workspace/[itemId]";

export const getExplorerRoute = (datasetId: string, query?: string): string => {
  const baseRoute = `/#/explorer/${datasetId}`;
  if (!query) return baseRoute;
  return query.startsWith("?") ? `${baseRoute}${query}` : `${baseRoute}?${query}`;
};

export const getWorkspaceRoute = (datasetId: string, itemId: string): string =>
  `/#/explorer/${datasetId}/workspace/${itemId}`;
