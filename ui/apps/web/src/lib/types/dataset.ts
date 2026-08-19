/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// ─── BaseSchema ────────────────────────────────────────────────────────────────

export enum BaseSchema {
  BBox = "BBox",
  Mask = "CompressedRLE",
  MultiPath = "MultiPath",
  Keypoints = "KeyPoints",
  Tracklet = "Tracklet",
  TextSpan = "TextSpan",
  Item = "Item",
  Source = "Source",
  Entity = "Entity",
  Image = "Image",
  SequenceFrame = "SequenceFrame",
  TextView = "Text",
  Feature = "Feature",
  Classification = "Classification",
  Conversation = "Conversation",
  Message = "Message",
}

// ─── WorkspaceType ─────────────────────────────────────────────────────────────

export enum WorkspaceType {
  IMAGE = "image",
  VIDEO = "video",
  IMAGE_VQA = "image_vqa",
  IMAGE_TEXT_ENTITY_LINKING = "image_text_entity_linking",
  PCL_3D = "3d", //forbidden to use "3D" as enum name
  UNDEFINED = "undefined",
}

// ─── Dataset Schema Types ──────────────────────────────────────────────────────

export interface FieldInfo {
  type: string;
  collection: boolean;
}
export interface DS_Schema {
  base_schema: BaseSchema;
  fields: Record<string, FieldInfo>;
  schema: string;
}

export interface DatasetSchema {
  relations: Record<string, string[]>;
  schemas: Record<string, DS_Schema>;
  groups: {
    annotations: string[];
    entities: string[];
    item: string[];
    views: string[];
    embeddings: string[];
  };
}

// ─── DatasetInfo ───────────────────────────────────────────────────────────────

export interface SchemaDescriptor {
  base?: string;
  name?: string;
  fields?: Record<string, { type?: string; collection?: boolean }>;
}

export interface DatasetInfoType {
  id: string;
  name: string;
  description: string;
  size: string;
  preview: string;
  workspace: string;
  num_items: number;
  views?: Record<string, SchemaDescriptor>;
  isFiltered?: boolean;
}

export class DatasetInfo implements DatasetInfoType {
  id: string;
  name: string;
  description: string;
  num_items: number;
  size: string;
  preview: string;
  workspace: WorkspaceType;
  views?: Record<string, SchemaDescriptor>;
  isFiltered?: boolean;

  constructor(obj: DatasetInfoType) {
    this.id = obj.id;
    this.name = obj.name;
    this.description = obj.description;
    this.num_items = obj.num_items;
    this.size = obj.size;
    this.preview = obj.preview;
    this.workspace = obj.workspace as WorkspaceType;
    this.views = obj.views;
    this.isFiltered = obj.isFiltered;
  }
}

export interface Dataset {
  id: string;
  path: string;
  previews_path: string;
  media_dir: string;
  thumbnail: string;
  schema: DatasetSchema;
  featureValues: object; //not used right now, maybe we will make a real type if needed
  info: DatasetInfo;
}
