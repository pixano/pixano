/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { apiMutate, apiMutateReturningRow, JSON_HEADERS, requestJson } from "./apiClient";

/** A row as the server stored it, as its API returns it. */
export type StoredRow = Record<string, unknown>;

function resourceUrl(datasetId: string, resource: string, _table: string, id?: string): string {
  const base = `/datasets/${datasetId}/${resource}`;
  const withId = id ? `${base}/${encodeURIComponent(id)}` : base;
  return withId;
}

export function getResource(
  datasetId: string,
  resource: string,
  table: string,
  id: string,
): Promise<StoredRow> {
  return requestJson<StoredRow>(
    resourceUrl(datasetId, resource, table, id),
    { headers: { Accept: JSON_HEADERS.Accept } },
    "getResource",
  );
}

export function createResource(
  datasetId: string,
  resource: string,
  table: string,
  body: Record<string, unknown>,
): Promise<StoredRow | undefined> {
  return apiMutateReturningRow(
    resourceUrl(datasetId, resource, table),
    { headers: JSON_HEADERS, method: "POST", body: JSON.stringify(body) },
    "createResource",
  );
}

export function updateResource(
  datasetId: string,
  resource: string,
  table: string,
  id: string,
  body: Record<string, unknown>,
): Promise<StoredRow | undefined> {
  const { id: _ignoredId, ...patch } = body;
  void _ignoredId;
  return apiMutateReturningRow(
    resourceUrl(datasetId, resource, table, id),
    { headers: JSON_HEADERS, method: "PUT", body: JSON.stringify(patch) },
    "updateResource",
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
