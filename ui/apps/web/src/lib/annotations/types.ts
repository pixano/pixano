/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Normalized xywh coordinates on the image (values in [0, 1]).
 * Mirrors pixano's BBoxData.coords shape.
 */
export type CoordsNorm = [number, number, number, number];

/**
 * Per-widget local box state. This is the source of truth for what the user sees
 * on the canvas; mutations to the backend are queued separately on the
 * WorkspaceManager's save queue.
 */
export interface LocalBBox {
  id: string;
  entityId: string;
  coordsNorm: CoordsNorm;
  /** True once the bbox (and its entity) have been POSTed to the backend. */
  persisted: boolean;
  /**
   * Snapshot of the parent entity's fields. Populated for persisted boxes so
   * UIs can display labels (e.g. `category` for VOCEntity) without an extra
   * fetch. Dataset-specific fields sit on the index signature.
   */
  entity?: Record<string, unknown>;
}

/**
 * Pick a human-friendly label from an entity row. Returns the first non-empty
 * string field that isn't an id / linkage column. Falls back to the entity id
 * (truncated) when no descriptive field exists so the user still has a handle.
 *
 * Keeping this generic means we don't have to hard-code `category` for VOC or
 * a different field for another dataset — the first user-facing string wins.
 */
const ENTITY_LABEL_SKIP = new Set([
  "id",
  "record_id",
  "parent_id",
  "entity_id",
  "created_at",
  "updated_at",
]);

export function pickEntityLabel(entity: Record<string, unknown> | undefined): string {
  if (!entity) return "";
  for (const [key, value] of Object.entries(entity)) {
    if (ENTITY_LABEL_SKIP.has(key)) continue;
    if (typeof value === "string" && value.trim().length > 0) return value;
  }
  const id = entity.id;
  return typeof id === "string" ? id.slice(0, 6) : "";
}

/**
 * Options attached to every image widget instance. `WorkspaceManager.selectRecordInDataset`
 * populates these so the widget can build valid BBox payloads without
 * having to reach back into global state.
 */
export interface ImageWidgetOptions {
  datasetId: string;
  recordId: string;
  viewId: string;
  viewName: string;
  imageWidth: number;
  imageHeight: number;
  [key: string]: unknown;
}

/**
 * Mutable per-instance storage for the image widget (managed via addStorage).
 * Lives in WorkspaceManager.storageMap, keyed by widget id.
 */
export interface ImageWidgetStorage {
  mode: "select" | "draw-bbox";
  selectedId: string | null;
  bboxes: LocalBBox[];
  [key: string]: unknown;
}

/**
 * A pending mutation to be flushed to the backend by WorkspaceManager.flushSave.
 * Modeled after pixano's ResourceMutation in apps/pixano/src/lib/api/resourcePayloads.ts.
 */
export type ResourceMutation =
  | {
      op: "create";
      resource: "entities" | "bboxes";
      body: Record<string, unknown>;
      /** Widget this mutation belongs to; used to flip `persisted` after success. */
      widgetId?: string;
      /** Local bbox id this mutation belongs to (for create/update/delete pairing). */
      localBBoxId?: string;
    }
  | {
      op: "update";
      resource: "bboxes";
      id: string;
      body: Record<string, unknown>;
      widgetId?: string;
      localBBoxId?: string;
    }
  | {
      op: "delete";
      resource: "bboxes" | "entities";
      id: string;
      widgetId?: string;
      localBBoxId?: string;
    };
