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
 * Minimal shape of a BBox3D row as returned by `GET /datasets/:id/bbox3ds`.
 * Mirrors the backend `BBox3D` LanceModel: 6 coords + 9-element row-major
 * rotation matrix. Format is either 'xyzwhd' (center + size) or 'xyzxyz'
 * (axis-aligned min/max corners). Confidence is -1 for ground truth.
 */
export interface BBox3DRow {
  id: string;
  record_id: string;
  entity_id: string;
  view_id: string;
  coords: [number, number, number, number, number, number];
  format: "xyzwhd" | "xyzxyz";
  rotation: number[];
  is_normalized: boolean;
  confidence?: number;
}

/**
 * Client-side augmentation of `BBox3DRow` with the parent entity row resolved
 * via `entity_id`. Mirrors the `LocalBBox.entity` pattern used for 2D boxes
 * so the 3D scene can render labels via `pickEntityLabel` without an extra
 * fetch. Datasets without entities (or with empty `entity_id`) leave this
 * undefined, in which case the scene draws no label.
 */
export type LocalBBox3D = BBox3DRow & { entity?: Record<string, unknown> };

interface PaginatedBBox3Ds {
  items: BBox3DRow[];
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

/**
 * List 3D bboxes for a (record, view) pair. Same query-param contract as
 * `listBBoxes`: `view_name` filters the `view_id` column server-side.
 */
export async function listBBox3Ds(
  datasetId: string,
  params: { recordId?: string; viewId?: string; limit?: number } = {},
): Promise<BBox3DRow[]> {
  const qs = new URLSearchParams();
  if (params.recordId) qs.set("record_id", params.recordId);
  if (params.viewId) qs.set("view_name", params.viewId);
  qs.set("limit", String(params.limit ?? 1000));
  const res = await requestJson<PaginatedBBox3Ds>(
    `${resourceUrl(datasetId, "bbox3ds")}?${qs.toString()}`,
    { headers: JSON_HEADERS, method: "GET" },
    "listBBox3Ds",
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

export async function deleteEntity(datasetId: string, id: string): Promise<void> {
  const res = await fetch(resourceUrl(datasetId, "entities", id), { method: "DELETE" });
  if (!res.ok && res.status !== 404) {
    throw new Error(`deleteEntity failed with ${res.status} ${res.statusText}`);
  }
}

export function createAnnotation(
  datasetId: string,
  resource: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(
    resourceUrl(datasetId, resource),
    { headers: JSON_HEADERS, method: "POST", body: JSON.stringify(body) },
    `createAnnotation(${resource})`,
  );
}

export function updateAnnotation(
  datasetId: string,
  resource: string,
  id: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const { id: _ignored, ...patch } = body;
  void _ignored;
  // Ask the backend to prune the previously attached entity when an entity_id
  // change leaves it orphaned (no-op for geometry-only edits).
  const url = `${resourceUrl(datasetId, resource, id)}?prune_orphan_entity=true`;
  return requestJson<Record<string, unknown>>(
    url,
    { headers: JSON_HEADERS, method: "PUT", body: JSON.stringify(patch) },
    `updateAnnotation(${resource})`,
  );
}

export async function deleteAnnotation(
  datasetId: string,
  resource: string,
  id: string,
): Promise<void> {
  // Ask the backend to also delete the parent entity when this was its last
  // annotation — the server is the only place that sees every reference.
  const url = `${resourceUrl(datasetId, resource, id)}?prune_orphan_entity=true`;
  const res = await fetch(url, { method: "DELETE" });
  if (!res.ok && res.status !== 404) {
    throw new Error(`deleteAnnotation(${resource}) failed with ${res.status} ${res.statusText}`);
  }
}
