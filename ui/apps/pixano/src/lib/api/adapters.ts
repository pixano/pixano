import type {
  DatasetInfoResponse,
  DatasetResponse,
  EntityResponse,
  ImageResponse,
  PaginatedResponse,
  PreviewDescriptor,
  RecordComponentResponse,
  RecordResponse,
  SFrameResponse,
  TextResponse,
} from "./restTypes";
import { normalizeTableName } from "./resourceNames";
import {
  BaseSchema,
  type Dataset,
  type DatasetBrowser,
  type DatasetInfo,
  type DatasetSchema,
  type DS_Schema,
  type RawSchemaData,
  type TableColumn,
  type TableRow,
} from "$lib/types/dataset";

const BASE_SCHEMA_BY_NAME: Record<string, BaseSchema> = {
  Record: BaseSchema.Item,
  Entity: BaseSchema.Entity,
  EntityDynamicState: BaseSchema.Classification,
  BBox: BaseSchema.BBox,
  CompressedRLE: BaseSchema.Mask,
  KeyPoints: BaseSchema.Keypoints,
  Tracklet: BaseSchema.Tracklet,
  Message: BaseSchema.Message,
  TextSpan: BaseSchema.TextSpan,
  Image: BaseSchema.Image,
  SequenceFrame: BaseSchema.SequenceFrame,
  Text: BaseSchema.TextView,
};

const ANNOTATION_TABLES = new Set([
  "bboxes",
  "masks",
  "keypoints",
  "tracklets",
  "messages",
  "text_spans",
  "entity_dynamic_states",
]);

function mapWorkspace(workspace: string): DatasetInfo["workspace"] {
  return workspace as DatasetInfo["workspace"];
}

function toFields(fields: Record<string, { type?: string; collection?: boolean }> = {}) {
  return Object.fromEntries(
    Object.entries(fields).map(([name, field]) => [
      name,
      {
        type: field.type ?? "str",
        collection: field.collection ?? false,
      },
    ]),
  );
}

function toDatasetSchemaEntry(
  base: string | undefined,
  fields: Record<string, { type?: string; collection?: boolean }> = {},
  schemaName?: string,
): DS_Schema {
  return {
    base_schema: BASE_SCHEMA_BY_NAME[base ?? ""] ?? BaseSchema.Item,
    fields: toFields(fields),
    schema: schemaName ?? base ?? "Unknown",
  };
}

export function toDatasetInfo(dto: DatasetInfoResponse): DatasetInfo {
  return {
    id: dto.id,
    name: dto.name,
    description: dto.description,
    size: dto.size,
    preview: dto.preview,
    workspace: mapWorkspace(dto.workspace),
    num_items: dto.num_records,
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
    let descriptor = undefined;
    if (normalizedTableName === "records") descriptor = info.record ?? undefined;
    else if (normalizedTableName === "entities") descriptor = info.entity ?? undefined;
    else if (normalizedTableName === "entity_dynamic_states")
      descriptor = info.entity_dynamic_state ?? undefined;
    else if (normalizedTableName === "bboxes") descriptor = info.bbox ?? undefined;
    else if (normalizedTableName === "masks") descriptor = info.mask ?? undefined;
    else if (normalizedTableName === "keypoints") descriptor = info.keypoint ?? undefined;
    else if (normalizedTableName === "tracklets") descriptor = info.tracklet ?? undefined;
    else if (normalizedTableName === "messages") descriptor = info.message ?? undefined;
    else if (normalizedTableName === "text_spans") descriptor = info.text_span ?? undefined;
    else if (info.views) {
      descriptor =
        Object.values(info.views).find((candidate) => candidate.name === schemaName) ?? undefined;
    }

    schemas[normalizedTableName] = toDatasetSchemaEntry(
      descriptor?.base ?? schemaName,
      descriptor?.fields ?? {},
      descriptor?.name ?? schemaName,
    );

    if (normalizedTableName === "records") groups.item.push(normalizedTableName);
    else if (normalizedTableName === "entities") groups.entities.push(normalizedTableName);
    else if (ANNOTATION_TABLES.has(normalizedTableName)) {
      groups.annotations.push(normalizedTableName);
    } else if (normalizedTableName === "embeddings") {
      groups.embeddings.push(normalizedTableName);
    } else {
      groups.views.push(normalizedTableName);
    }
  }

  return {
    relations: {},
    schemas,
    groups,
  };
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

function inferColumnType(value: unknown): string {
  if (typeof value === "number") return Number.isInteger(value) ? "int" : "float";
  if (typeof value === "boolean") return "bool";
  return "str";
}

export function toDatasetBrowser(
  datasetId: string,
  records: PaginatedResponse<RecordResponse>,
  sort?: { col: string; order: string },
): DatasetBrowser {
  const items = [...records.items];
  if (sort?.col) {
    items.sort((left, right) => {
      const leftValue = left[sort.col];
      const rightValue = right[sort.col];
      const cmp = String(leftValue ?? "").localeCompare(String(rightValue ?? ""));
      return sort.order === "desc" ? -cmp : cmp;
    });
  }

  const columnsMap = new Map<string, string>();
  const viewColumns = new Map<string, string>();
  const rows: TableRow[] = items.map((record) => {
    const row: TableRow = {};
    for (const [key, value] of Object.entries(record)) {
      if (typeof value === "object" && value !== null) continue;
      row[key] = (value ?? "") as string | number | boolean;
      if (!columnsMap.has(key)) {
        columnsMap.set(key, inferColumnType(value));
      }
    }

    const viewPreviews = record.view_previews as Record<string, PreviewDescriptor> | undefined;
    for (const [logicalName, preview] of Object.entries(viewPreviews ?? {})) {
      row[logicalName] = preview.preview_url;
      viewColumns.set(logicalName, preview.kind);
    }

    return row;
  });

  const columns: TableColumn[] = [
    ...Array.from(viewColumns.entries()).map(([name, type]) => ({ name, type })),
    ...Array.from(columnsMap.entries()).map(([name, type]) => ({
      name,
      type,
    })),
  ];

  return {
    id: datasetId,
    name: datasetId,
    table_data: {
      columns,
      rows,
    },
    pagination: {
      current_page: Math.floor(records.offset / Math.max(records.limit, 1)) + 1,
      page_size: records.limit,
      total_size: records.total,
    },
    semantic_search: [],
  };
}

function tableInfo(name: string, group: string, baseSchema: BaseSchema) {
  return {
    name,
    group,
    base_schema: baseSchema,
  } as const;
}

function baseSchemaFromTableName(tableName: string): BaseSchema {
  switch (normalizeTableName(tableName)) {
    case "bboxes":
      return BaseSchema.BBox;
    case "masks":
      return BaseSchema.Mask;
    case "keypoints":
      return BaseSchema.Keypoints;
    case "tracklets":
      return BaseSchema.Tracklet;
    case "messages":
      return BaseSchema.Message;
    case "text_spans":
      return BaseSchema.TextSpan;
    case "entity_dynamic_states":
      return BaseSchema.Classification;
    default:
      return BaseSchema.Classification;
  }
}

export function toRawRecord(record: RecordResponse, tableName = "records"): RawSchemaData {
  const { id, created_at = "", updated_at = "", ...data } = record;
  return {
    id,
    created_at,
    updated_at,
    table_info: tableInfo(normalizeTableName(tableName), "item", BaseSchema.Item),
    data,
  };
}

export function toRawEntity(entity: EntityResponse, tableName = "entities"): RawSchemaData {
  const {
    id,
    created_at = "",
    updated_at = "",
    record_id = "",
    parent_id = "",
    ...data
  } = entity;
  return {
    id,
    created_at,
    updated_at,
    table_info: tableInfo(normalizeTableName(tableName), "entities", BaseSchema.Entity),
    data: {
      item_id: record_id,
      parent_id,
      ...data,
    },
  };
}

export function toRawView(view: ImageResponse | SFrameResponse | TextResponse): RawSchemaData {
  const {
    id,
    created_at = "",
    updated_at = "",
    record_id = "",
    logical_name = "",
  } = view;
  const src = "src" in view ? view.src : undefined;
  const width = "width" in view ? view.width : undefined;
  const height = "height" in view ? view.height : undefined;
  const format = "format" in view ? view.format : undefined;
  const content = "content" in view ? view.content : undefined;
  const uri = "uri" in view ? view.uri : undefined;
  const frame_index = "frame_index" in view ? view.frame_index : undefined;
  const timestamp = "timestamp" in view ? view.timestamp : undefined;
  const isText = "content" in view || "uri" in view;
  const isSequenceFrame = typeof frame_index === "number";

  return {
    id,
    created_at,
    updated_at,
    table_info: tableInfo(
      isText ? "texts" : isSequenceFrame ? "sequence_frames" : "images",
      "views",
      isText ? BaseSchema.TextView : isSequenceFrame ? BaseSchema.SequenceFrame : BaseSchema.Image,
    ),
    data: {
      item_id: record_id,
      parent_id: "",
      view_name: logical_name,
      url: src,
      content,
      uri,
      width,
      height,
      format,
      frame_index,
      timestamp,
    },
  };
}

export function toRawAnnotation(
  component: RecordComponentResponse,
  viewNamesById: Map<string, string>,
  tableName: string,
): RawSchemaData {
  const {
    id,
    created_at = "",
    updated_at = "",
    record_id = "",
    view_id,
    frame_id,
    source_type,
    source_name,
    source_metadata,
    ...data
  } = component;
  const normalizedTableName = normalizeTableName(tableName);
  // Use frame_id (if present) to resolve the view_name for display, but preserve
  // the original view_id so that tracklets and per-frame annotations share the same value.
  const inferredViewId = typeof frame_id === "string" && frame_id !== "" ? frame_id : view_id;

  const result = {
    id,
    created_at,
    updated_at,
    table_info: tableInfo(normalizedTableName, "annotations", baseSchemaFromTableName(tableName)),
    data: {
      record_id,
      item_id: record_id,
      view_id: typeof view_id === "string" ? view_id : "",
      frame_id: typeof frame_id === "string" ? frame_id : "",
      source_type,
      source_name,
      view_name:
        typeof inferredViewId === "string" && inferredViewId !== ""
          ? (viewNamesById.get(inferredViewId) ?? "")
          : "",
      inference_metadata: {},
      source_metadata,
      ...data,
    },
  };

  // Reverse-map backend field names for tracklets
  if (normalizedTableName === "tracklets") {
    const d = result.data as Record<string, unknown>;
    if ("start_timestep" in d) { d.start_frame = d.start_timestep; delete d.start_timestep; }
    if ("end_timestep" in d) { d.end_frame = d.end_timestep; delete d.end_timestep; }
  }

  return result;
}
