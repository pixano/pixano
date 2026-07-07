/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface DatasetInfoResponse {
  id: string;
  name: string;
  description: string;
  size: string;
  preview: string;
  workspace: string;
  storage_mode: string;
  num_records: number;
  record?: SchemaDescriptor | null;
  entity?: SchemaDescriptor | null;
  entity_dynamic_state?: SchemaDescriptor | null;
  bbox?: SchemaDescriptor | null;
  mask?: SchemaDescriptor | null;
  keypoint?: SchemaDescriptor | null;
  tracklet?: SchemaDescriptor | null;
  message?: SchemaDescriptor | null;
  text_span?: SchemaDescriptor | null;
  views?: Record<string, SchemaDescriptor>;
}

export interface DatasetResponse {
  id: string;
  path: string;
  previews_path: string;
  thumbnail: string;
  tables: Record<string, string>;
  feature_values: Record<string, unknown>;
  info: DatasetInfoResponse;
}

export interface SchemaFieldDescriptor {
  type?: string;
  collection?: boolean;
}

export interface SchemaDescriptor {
  base?: string;
  name?: string;
  fields?: Record<string, SchemaFieldDescriptor>;
}

export interface RecordResponse {
  id: string;
  split?: string;
  created_at?: string;
  updated_at?: string;
  view_previews?: Record<string, PreviewDescriptor>;
  [key: string]: unknown;
}

export interface PreviewDescriptor {
  resource: string;
  id: string;
  kind: string;
  preview_url: string;
}

export interface RecordComponentResponse {
  id: string;
  record_id?: string;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface ImageResponse {
  id: string;
  record_id: string;
  logical_name?: string;
  created_at?: string;
  updated_at?: string;
  width?: number;
  height?: number;
  format?: string;
  src: string;
}

export interface TextResponse {
  id: string;
  record_id: string;
  logical_name?: string;
  created_at?: string;
  updated_at?: string;
  content?: string;
  uri?: string;
}

export interface SFrameResponse {
  id: string;
  record_id: string;
  logical_name?: string;
  created_at?: string;
  updated_at?: string;
  width?: number;
  height?: number;
  format?: string;
  src: string;
  frame_index?: number;
  timestamp?: number;
}

export interface EntityResponse extends RecordComponentResponse {
  parent_id?: string;
}

/** One data format registered with the import/export registry. */
export interface IoFormatResponse {
  name: string;
  title: string;
  can_import: boolean;
  can_export: boolean;
  capabilities: {
    media_kinds: string[];
    annotation_kinds: string[];
    supports_resume: boolean;
  };
}

/** Provenance of one finding sample (file:line style locations). */
export interface IoProvenance {
  file?: string | null;
  line?: number | null;
  json_pointer?: string | null;
  record_key?: string | null;
}

/** One aggregated validation finding from analyze. */
export interface IoFinding {
  code: string;
  severity: "error" | "warning" | "info";
  count: number;
  samples: IoProvenance[];
  suggestion: string;
}

/** The analyze plan the wizard previews before ingesting. */
export interface ImportPlanResponse {
  format: string;
  importer_version: string;
  splits: Record<string, number>;
  totals: { records: number | null; media_bytes: number | null; estimated: boolean };
  report: { findings: Record<string, IoFinding> };
  previews: { record: Record<string, unknown>; thumbnails: Record<string, string> }[];
  plan_id?: string;
}

/** One durable import/export job as stored. */
export interface IoJobResponse {
  job_id: string;
  kind: string;
  dataset: string;
  status: "pending" | "running" | "interrupted" | "done" | "error" | "cancelled" | "rolled_back";
  progress: {
    phase?: string;
    done?: number;
    total?: number | null;
    table_counts?: Record<string, number>;
    message?: string;
  };
  error: { type?: string; message?: string };
  created_at: number;
  updated_at: number;
}
