/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { annotationsForTask, attrsPayload, validateAttrRows, type AttrRow } from "./rawSchema";

/** User annotation settings, independent of raw-media layout and video options. */
export interface LerobotFields {
  recordAttrs: AttrRow[];
  entityAttrs: AttrRow[];
  annotations: string[];
}

export const DEFAULT_LEROBOT_FIELDS: LerobotFields = {
  recordAttrs: [],
  entityAttrs: [],
  annotations: ["bbox", "mask", "tracklet"],
};

const RECORD_FIELDS = new Set([
  "id",
  "split",
  "created_at",
  "updated_at",
  "status",
  "comment",
  "episode_index",
  "tasks",
  "length",
]);
const ENTITY_FIELDS = new Set(["id", "record_id", "parent_id"]);

/** Validate annotation settings before requesting a LeRobot import plan. */
export function validateLerobotFields(fields: LerobotFields): string {
  const recordError = validateAttrRows(fields.recordAttrs, "Record attribute");
  if (recordError) return recordError;
  const entityError = validateAttrRows(fields.entityAttrs, "Object attribute");
  if (entityError) return entityError;
  for (const row of [...fields.recordAttrs, ...fields.entityAttrs]) {
    if (row.name.startsWith("model_")) {
      return `Attribute '${row.name}' uses the reserved model_ prefix. Choose another name.`;
    }
  }
  for (const row of fields.recordAttrs) {
    if (RECORD_FIELDS.has(row.name)) {
      return `Record attribute '${row.name}' is provided by Pixano or the LeRobot source. Choose another name.`;
    }
    if (row.required) {
      return `Record attribute '${row.name}' cannot be required: its value is filled in after import.`;
    }
  }
  for (const row of fields.entityAttrs) {
    if (ENTITY_FIELDS.has(row.name)) {
      return `Object attribute '${row.name}' is managed by Pixano. Choose another name.`;
    }
  }
  return "";
}

/** Leave cameras, episode fields, workspace, and vectors to source-aware inference. */
export function buildLerobotSchemaSpec(fields: LerobotFields): Record<string, unknown> {
  const schema: Record<string, unknown> = {
    annotations: annotationsForTask("video", fields.annotations),
  };
  if (fields.recordAttrs.length) schema.record = { attrs: attrsPayload(fields.recordAttrs) };
  if (fields.entityAttrs.length) schema.entity = { attrs: attrsPayload(fields.entityAttrs) };
  return schema;
}
