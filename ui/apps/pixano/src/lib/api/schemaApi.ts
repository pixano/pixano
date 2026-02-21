/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Schema } from "$lib/types/dataset";
import * as utils from "$lib/utils/coreUtils";

import { apiMutate, JSON_HEADERS } from "./apiClient";

// ─── addSchema ──────────────────────────────────────────────────────────────────

export function addSchema(route: string, ds_id: string, sch: Schema, no_table: boolean) {
  const url = no_table
    ? `/${route}/${ds_id}/${sch.id}`
    : `/${route}/${ds_id}/${sch.table_info.name}/${sch.id}`;
  return apiMutate(
    url,
    { headers: JSON_HEADERS, method: "POST", body: JSON.stringify(sch) },
    "addSchema",
  );
}

// ─── addSchemas ─────────────────────────────────────────────────────────────────

export function addSchemas(
  route: string,
  ds_id: string,
  schs: Schema[],
  table: string,
  no_table: boolean,
) {
  const url = no_table ? `/${route}/${ds_id}` : `/${route}/${ds_id}/${table}`;
  return apiMutate(
    url,
    { headers: JSON_HEADERS, method: "POST", body: JSON.stringify(schs) },
    "addSchemas",
  );
}

// ─── updateSchema ───────────────────────────────────────────────────────────────

export function updateSchema(route: string, ds_id: string, sch: Schema, no_table: boolean) {
  const url = no_table
    ? `/${route}/${ds_id}/${sch.id}`
    : `/${route}/${ds_id}/${sch.table_info.name}/${sch.id}`;
  return apiMutate(
    url,
    { headers: JSON_HEADERS, method: "PUT", body: JSON.stringify(sch) },
    "updateSchema",
  );
}

// ─── updateSchemas ──────────────────────────────────────────────────────────────

export function updateSchemas(
  route: string,
  ds_id: string,
  schs: Schema[],
  table: string,
  no_table: boolean,
) {
  const url = no_table ? `/${route}/${ds_id}` : `/${route}/${ds_id}/${table}`;
  return apiMutate(
    url,
    { headers: JSON_HEADERS, method: "PUT", body: JSON.stringify(schs) },
    "updateSchemas",
  );
}

// ─── deleteSchemasByIds ─────────────────────────────────────────────────────────

export async function deleteSchemasByIds(
  route: string,
  ds_id: string,
  sch_ids: string[],
  table_name: string,
  no_table: boolean,
) {
  const base_url = no_table ? `/${route}/${ds_id}?ids=` : `/${route}/${ds_id}/${table_name}?ids=`;
  const url_chunks = utils.splitWithLimit(sch_ids, "&ids=", 8000);
  await Promise.all(
    url_chunks.map((ids_query) =>
      apiMutate(base_url + ids_query, { method: "DELETE" }, "deleteSchema"),
    ),
  );
}
