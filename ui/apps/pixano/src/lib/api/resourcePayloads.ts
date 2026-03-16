/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { views } from "$lib/stores/workspaceStores.svelte";
import { BaseSchema, Message, type Schema } from "$lib/types/dataset";
import { rleToString } from "$lib/utils/maskUtils";
import { toMessageTransportPayload } from "$lib/utils/messageUtils";

export interface MutationTarget {
  resource: string;
  id: string;
}

export interface ResourceMutation {
  op: "create" | "update" | "delete";
  target: MutationTarget;
  body?: Record<string, unknown>;
  schema: Schema;
}

const RESOURCE_BY_BASE_SCHEMA: Partial<Record<BaseSchema, string>> = {
  [BaseSchema.Item]: "records",
  [BaseSchema.Entity]: "entities",
  [BaseSchema.Tracklet]: "tracklets",
  [BaseSchema.BBox]: "bboxes",
  [BaseSchema.Mask]: "masks",
  [BaseSchema.Keypoints]: "keypoints",
  [BaseSchema.TextSpan]: "text-spans",
  [BaseSchema.Message]: "messages",
};

const SHARED_EXCLUDED_FIELDS = new Set([
  "item_id",
  "view_name",
  "source_id",
  "timestamp",
  "inference_metadata",
]);

function withoutUndefined<T extends Record<string, unknown>>(payload: T): T {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => value !== undefined),
  ) as T;
}

function resolveViewId(schema: Schema): string {
  const data = schema.data as Record<string, unknown>;
  const explicitViewId = data.view_id;
  if (typeof explicitViewId === "string" && explicitViewId !== "") {
    return explicitViewId;
  }

  const viewName = data.view_name;
  if (typeof viewName !== "string" || viewName === "") {
    return "";
  }

  const currentView = views.value[viewName];
  if (!currentView) {
    return "";
  }
  if (Array.isArray(currentView)) {
    return currentView.length > 0 ? currentView[0].id : "";
  }

  return currentView.id;
}

function normalizeBasePayload(schema: Schema): Record<string, unknown> {
  const rawData = schema.data as Record<string, unknown>;
  const data = Object.fromEntries(
    Object.entries(rawData).filter(([key]) => !SHARED_EXCLUDED_FIELDS.has(key)),
  );

  const record_id =
    typeof rawData.record_id === "string" && rawData.record_id !== ""
      ? rawData.record_id
      : typeof rawData.item_id === "string"
        ? rawData.item_id
        : "";

  const payload = {
    id: schema.id,
    ...data,
    record_id,
    source_type: typeof rawData.source_type === "string" ? rawData.source_type : undefined,
    source_name: typeof rawData.source_name === "string" ? rawData.source_name : undefined,
    source_metadata:
      typeof rawData.source_metadata === "string"
        ? rawData.source_metadata
        : rawData.source_metadata !== undefined
          ? JSON.stringify(rawData.source_metadata)
          : undefined,
  } satisfies Record<string, unknown>;

  return withoutUndefined(payload);
}

function serializeEntity(schema: Schema): Record<string, unknown> {
  const payload = normalizeBasePayload(schema);
  delete payload.view_id;
  delete payload.frame_id;
  delete payload.frame_index;
  delete payload.entity_id;
  delete payload.tracklet_id;
  delete payload.entity_dynamic_state_id;
  return payload;
}

function serializeTracklet(schema: Schema): Record<string, unknown> {
  const payload = normalizeBasePayload(schema);
  payload.view_id = resolveViewId(schema);
  if ("start_frame" in payload) {
    payload.start_timestep = payload.start_frame;
    delete payload.start_frame;
  }
  if ("end_frame" in payload) {
    payload.end_timestep = payload.end_frame;
    delete payload.end_frame;
  }
  return withoutUndefined(payload);
}

function serializeAnnotation(schema: Schema): Record<string, unknown> {
  const payload = normalizeBasePayload(schema);
  payload.view_id = resolveViewId(schema);

  if (schema.table_info.base_schema === BaseSchema.Mask && Array.isArray(payload.counts)) {
    payload.counts = rleToString(payload.counts as number[]);
  }

  return withoutUndefined(payload);
}

function serializeRecord(schema: Schema): Record<string, unknown> {
  return withoutUndefined({ id: schema.id, ...schema.data });
}

export function serializeSchema(schema: Schema): Record<string, unknown> {
  switch (schema.table_info.base_schema) {
    case BaseSchema.Item:
      return serializeRecord(schema);
    case BaseSchema.Entity:
      return serializeEntity(schema);
    case BaseSchema.Tracklet:
      return serializeTracklet(schema);
    case BaseSchema.BBox:
    case BaseSchema.Mask:
    case BaseSchema.Keypoints:
    case BaseSchema.TextSpan:
      return serializeAnnotation(schema);
    case BaseSchema.Message:
      return toMessageTransportPayload(schema as Message) as unknown as Record<string, unknown>;
    default:
      throw new Error(`Unsupported resource serialization for '${schema.table_info.base_schema}'.`);
  }
}

export function resourceForSchema(schema: Schema): string {
  const resource = RESOURCE_BY_BASE_SCHEMA[schema.table_info.base_schema];
  if (!resource) {
    throw new Error(`Unsupported resource '${schema.table_info.base_schema}' for persistence.`);
  }
  return resource;
}

export function toResourceMutation(
  changeType: ResourceMutation["op"],
  schema: Schema,
): ResourceMutation {
  return {
    op: changeType,
    target: {
      resource: resourceForSchema(schema),
      id: schema.id,
    },
    body: changeType === "delete" ? undefined : serializeSchema(schema),
    schema,
  };
}
