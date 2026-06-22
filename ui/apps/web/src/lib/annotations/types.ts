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
 * Camera intrinsics and extrinsics from a CalibratedImage view.
 * All matrices are row-major, 4×4 flattened to 16 floats.
 */
export interface CameraCalibration {
  f: [number, number];
  c: [number, number];
  distortion: number[];
  extrinsicMatrix: number[];
  egoToWorld: number[];
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
  calibration: CameraCalibration | null;
  [key: string]: unknown;
}

/**
 * Mutable per-instance storage for the image widget (managed via addStorage).
 * Lives in WorkspaceManager.storageMap, keyed by widget id. Annotation state
 * is NOT here — it lives on the record's shared collection
 * (`WorkspaceSession.annotations`); storage holds genuinely per-widget state.
 */
export interface ImageWidgetStorage {
  /** Id of the active tool from the 2D tool registry. */
  activeToolId: string;
  [key: string]: unknown;
}

/**
 * Mutable per-instance storage for the point-cloud widget.
 */
export interface PointCloudWidgetStorage {
  /** Id of the active tool from the 3D tool registry. */
  activeToolId: string;
  [key: string]: unknown;
}

/**
 * The user's entity decision for a freshly drawn box, collected by the
 * Inspector's SaveAnnotationForm: either link to an existing entity or create
 * a new one with the given (schema-derived) feature fields.
 */
export type PendingEntityChoice =
  | { mode: "existing"; entityId: string }
  | { mode: "new"; entityFields: Record<string, unknown> };

/**
 * A box that has been drawn but not yet committed: it waits for the user to
 * pick or create its entity in the Inspector. The originating widget supplies
 * the callbacks so the domain logic (building mutations) stays widget-local
 * while the form stays presentational. Mirrors pixano's `newShape("saving")`.
 */
export interface PendingAnnotation {
  /** Human label for the form header, e.g. "box" or "3D box". */
  label: string;
  onConfirm: (choice: PendingEntityChoice) => void;
  onCancel: () => void;
}

/**
 * A pending mutation to be flushed to the backend by WorkspaceManager.flushSave.
 * Modeled after pixano's ResourceMutation in apps/pixano/src/lib/api/resourcePayloads.ts.
 */
export type ResourceMutation =
  | {
      op: "create";
      resource: string;
      body: Record<string, unknown>;
      /** Widget this mutation belongs to; used to flip `persisted` after success. */
      widgetId?: string;
      /** Local annotation id this mutation belongs to (for create/update/delete pairing). */
      localAnnotationId?: string;
    }
  | {
      op: "update";
      resource: string;
      id: string;
      body: Record<string, unknown>;
      widgetId?: string;
      localAnnotationId?: string;
    }
  | {
      op: "delete";
      resource: string;
      id: string;
      widgetId?: string;
      localAnnotationId?: string;
    };
