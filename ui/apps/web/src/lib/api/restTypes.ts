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
