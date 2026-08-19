/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { normalizeTableName } from "./resourceNames";
import type { DatasetInfoResponse, DatasetResponse } from "./restTypes";
import {
  BaseSchema,
  type Dataset,
  type DatasetInfo,
  type DatasetSchema,
  type DS_Schema,
} from "$lib/types/dataset";

// ─── Schema registries ────────────────────────────────────────────────────────

/** Maps backend schema-class names → BaseSchema enum. */
const SCHEMA_NAME_TO_BASE: Record<string, BaseSchema> = {
  Record: BaseSchema.Item,
  Entity: BaseSchema.Entity,
  EntityDynamicState: BaseSchema.Classification,
  BBox: BaseSchema.BBox,
  CompressedRLE: BaseSchema.Mask,
  MultiPath: BaseSchema.MultiPath,
  KeyPoints: BaseSchema.Keypoints,
  Tracklet: BaseSchema.Tracklet,
  Message: BaseSchema.Message,
  TextSpan: BaseSchema.TextSpan,
  Image: BaseSchema.Image,
  SequenceFrame: BaseSchema.SequenceFrame,
  Text: BaseSchema.TextView,
};

/** Maps normalized table names → the corresponding key on DatasetInfoResponse. */
type InfoDescriptorKey = keyof Pick<
  DatasetInfoResponse,
  | "record"
  | "entity"
  | "entity_dynamic_state"
  | "bbox"
  | "mask"
  | "keypoint"
  | "tracklet"
  | "message"
  | "text_span"
>;

const DESCRIPTOR_KEY_BY_TABLE: Partial<Record<string, InfoDescriptorKey>> = {
  records: "record",
  entities: "entity",
  entity_dynamic_states: "entity_dynamic_state",
  bboxes: "bbox",
  masks: "mask",
  keypoints: "keypoint",
  tracklets: "tracklet",
  messages: "message",
  text_spans: "text_span",
};

const ANNOTATION_TABLES = new Set([
  "bboxes",
  "masks",
  "multi_paths",
  "keypoints",
  "tracklets",
  "messages",
  "text_spans",
  "entity_dynamic_states",
]);

// ─── Helpers ──────────────────────────────────────────────────────────────────

function mapWorkspace(workspace: string): DatasetInfo["workspace"] {
  return workspace as DatasetInfo["workspace"];
}

function toFields(fields: Record<string, { type?: string; collection?: boolean }> = {}) {
  return Object.fromEntries(
    Object.entries(fields).map(([name, field]) => [
      name,
      { type: field.type ?? "str", collection: field.collection ?? false },
    ]),
  );
}

function toDatasetSchemaEntry(
  base: string | undefined,
  fields: Record<string, { type?: string; collection?: boolean }> = {},
  schemaName?: string,
): DS_Schema {
  return {
    base_schema: SCHEMA_NAME_TO_BASE[base ?? ""] ?? BaseSchema.Item,
    fields: toFields(fields),
    schema: schemaName ?? base ?? "Unknown",
  };
}

// ─── Public adapters ──────────────────────────────────────────────────────────

export function toDatasetInfo(dto: DatasetInfoResponse): DatasetInfo {
  return {
    id: dto.id,
    name: dto.name,
    description: dto.description,
    size: dto.size,
    preview: dto.preview,
    workspace: mapWorkspace(dto.workspace),
    num_items: dto.num_records,
    views: dto.views,
  };
}

export function toDatasetSchema(dto: DatasetResponse): DatasetSchema {
  const schemas: DatasetSchema["schemas"] = {};
  const groups: DatasetSchema["groups"] = {
    annotations: [],
    entities: [],
    item: [],
    views: [],
    embeddings: [],
  };

  for (const [tableName, schemaName] of Object.entries(dto.tables)) {
    const normalizedTableName = normalizeTableName(tableName);
    const info = dto.info;

    const infoKey = DESCRIPTOR_KEY_BY_TABLE[normalizedTableName];
    const descriptor = infoKey
      ? (info[infoKey] ?? undefined)
      : info.views
        ? (Object.values(info.views).find((c) => c.name === schemaName) ?? undefined)
        : undefined;

    schemas[normalizedTableName] = toDatasetSchemaEntry(
      descriptor?.base ?? schemaName,
      descriptor?.fields ?? {},
      descriptor?.name ?? schemaName,
    );

    if (normalizedTableName === "records") groups.item.push(normalizedTableName);
    else if (normalizedTableName === "entities") groups.entities.push(normalizedTableName);
    else if (ANNOTATION_TABLES.has(normalizedTableName))
      groups.annotations.push(normalizedTableName);
    else if (normalizedTableName === "embeddings") groups.embeddings.push(normalizedTableName);
    else groups.views.push(normalizedTableName);
  }

  return { relations: {}, schemas, groups };
}

export function toDataset(dto: DatasetResponse): Dataset {
  return {
    id: dto.id,
    path: dto.path,
    previews_path: dto.previews_path,
    media_dir: dto.path,
    thumbnail: dto.thumbnail,
    schema: toDatasetSchema(dto),
    featureValues: dto.feature_values,
    info: toDatasetInfo(dto.info),
  };
}
