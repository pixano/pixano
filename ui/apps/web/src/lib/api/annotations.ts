/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { JSON_HEADERS, requestJson } from "./apiClient";

/**
 * Minimal POST/PUT/DELETE wrappers for the REST resources used by 2D box
 * annotations. Ported from ui/apps/pixano/src/lib/api/schemaApi.ts but trimmed
 * down to only the `entities` and `bboxes` resources that the web app needs.
 */

function resourceUrl(datasetId: string, resource: string, id?: string): string {
  const base = `/datasets/${datasetId}/${resource}`;
  return id ? `${base}/${encodeURIComponent(id)}` : base;
}

/**
 * Minimal shape of a BBox row as returned by `GET /datasets/:id/bboxes`.
 * We intentionally only type the fields we consume client-side; extra columns
 * (source_*, tracklet_id, frame_id, …) still come through in the payload.
 */
export interface BBoxRow {
  id: string;
  record_id: string;
  entity_id: string;
  view_id: string;
  coords: [number, number, number, number];
  format: "xywh" | "xyxy";
  is_normalized: boolean;
  confidence?: number;
}

interface PaginatedBBoxes {
  items: BBoxRow[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Minimal shape of an Entity row. The backend Entity schema only guarantees
 * `id`, `record_id` and `parent_id`; dataset-specific subclasses add custom
 * fields (e.g. VOCEntity adds `category` and `is_difficult`). We keep those
 * generic via an index signature.
 */
export interface EntityRow {
  id: string;
  record_id: string;
  parent_id?: string;
  [key: string]: unknown;
}

interface PaginatedEntities {
  items: EntityRow[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * List entities for a record. Mirrors `listBBoxes` — see
 * `src/pixano/api/resources.py` for the list filters accepted by the backend.
 */
export async function listEntities(
  datasetId: string,
  params: { recordId?: string; limit?: number } = {},
): Promise<EntityRow[]> {
  const qs = new URLSearchParams();
  if (params.recordId) qs.set("record_id", params.recordId);
  qs.set("limit", String(params.limit ?? 1000));
  const res = await requestJson<PaginatedEntities>(
    `${resourceUrl(datasetId, "entities")}?${qs.toString()}`,
    { headers: JSON_HEADERS, method: "GET" },
    "listEntities",
  );
  return res.items ?? [];
}

/**
 * List bboxes from the backend. The server accepts `record_id`, `view_name`
 * (which actually filters on the `view_id` column for annotations — see
 * `service.list` in src/pixano/api/service.py), `entity_id`, `source_type`
 * and a free-form `where` clause.
 */
export async function listBBoxes(
  datasetId: string,
  params: { recordId?: string; viewId?: string; limit?: number } = {},
): Promise<BBoxRow[]> {
  const qs = new URLSearchParams();
  if (params.recordId) qs.set("record_id", params.recordId);
  // Annotation endpoints use the `view_name` query param name to filter the
  // `view_id` column — legacy naming.
  if (params.viewId) qs.set("view_name", params.viewId);
  qs.set("limit", String(params.limit ?? 1000));
  const res = await requestJson<PaginatedBBoxes>(
    `${resourceUrl(datasetId, "bboxes")}?${qs.toString()}`,
    { headers: JSON_HEADERS, method: "GET" },
    "listBBoxes",
  );
  return res.items ?? [];
}

export function createEntity(
  datasetId: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(
    resourceUrl(datasetId, "entities"),
    { headers: JSON_HEADERS, method: "POST", body: JSON.stringify(body) },
    "createEntity",
  );
}

export function createBBox(
  datasetId: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(
    resourceUrl(datasetId, "bboxes"),
    { headers: JSON_HEADERS, method: "POST", body: JSON.stringify(body) },
    "createBBox",
  );
}

export function updateBBox(
  datasetId: string,
  id: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const { id: _ignored, ...patch } = body;
  void _ignored;
  return requestJson<Record<string, unknown>>(
    resourceUrl(datasetId, "bboxes", id),
    { headers: JSON_HEADERS, method: "PUT", body: JSON.stringify(patch) },
    "updateBBox",
  );
}

export async function deleteBBox(datasetId: string, id: string): Promise<void> {
  const res = await fetch(resourceUrl(datasetId, "bboxes", id), { method: "DELETE" });
  if (!res.ok && res.status !== 404) {
    throw new Error(`deleteBBox failed with ${res.status} ${res.statusText}`);
  }
}

export async function deleteEntity(datasetId: string, id: string): Promise<void> {
  const res = await fetch(resourceUrl(datasetId, "entities", id), { method: "DELETE" });
  if (!res.ok && res.status !== 404) {
    throw new Error(`deleteEntity failed with ${res.status} ${res.statusText}`);
  }
}
