/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { apiMutate, JSON_HEADERS } from "./apiClient";

function resourceUrl(datasetId: string, resource: string, _table: string, id?: string): string {
  const base = `/datasets/${datasetId}/${resource}`;
  const withId = id ? `${base}/${encodeURIComponent(id)}` : base;
  return withId;
}

export function createResource(
  datasetId: string,
  resource: string,
  table: string,
  body: Record<string, unknown>,
) {
  return apiMutate(
    resourceUrl(datasetId, resource, table),
    { headers: JSON_HEADERS, method: "POST", body: JSON.stringify(body) },
    "createResource",
    true,
  );
}

export function updateResource(
  datasetId: string,
  resource: string,
  table: string,
  id: string,
  body: Record<string, unknown>,
) {
  const { id: _ignoredId, ...patch } = body;
  void _ignoredId;
  return apiMutate(
    resourceUrl(datasetId, resource, table, id),
    { headers: JSON_HEADERS, method: "PUT", body: JSON.stringify(patch) },
    "updateResource",
    true,
  );
}

export function deleteResource(datasetId: string, resource: string, table: string, id: string) {
  return apiMutate(
    resourceUrl(datasetId, resource, table, id),
    { method: "DELETE" },
    "deleteResource",
    true,
    [404],
  );
}
