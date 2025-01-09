/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import type { Annotation } from "./annotations";
import { BaseSchema } from "./BaseSchema";
import type { DatasetInfo } from "./DatasetInfo";
import type { DatasetItem } from "./DatasetItem";
import type { Entity } from "./entities";
import type { Item } from "./items";
import type { Source } from "./sources";

////////// TYPES /////////////
export const referenceSchema = z
  .object({
    id: z.string(),
    name: z.string(),
  })
  .strict();
export type Reference = z.infer<typeof referenceSchema>;

export const ndArrayFloatSchema = z
  .object({
    values: z.array(z.number()),
    shape: z.array(z.number()),
  })
  .strict();
export type NDArrayFloat = z.infer<typeof ndArrayFloatSchema>;

export const tableInfoSchema = z
  .object({
    name: z.string(),
    group: z.string(),
    base_schema: z.nativeEnum(BaseSchema),
  })
  .strict();
export type TableInfo = z.infer<typeof tableInfoSchema>;

//note: this one is needed only to parse in BaseData<T> constructor
//because I can't find a way to parse with the generic typed version
export const refDataFieldsSchema = z
  .object({
    id: z.string(),
    table_info: tableInfoSchema,
    created_at: z.string(),
    updated_at: z.string(),
    data: z.any(),
  })
  .strict();
export const baseDataFieldsSchema = <T extends z.ZodType>(schema: T) => {
  return z
    .object({
      id: z.string(),
      table_info: tableInfoSchema,
      created_at: z.string(),
      updated_at: z.string(),
      data: schema,
    })
    .strict();
};
type BaseDataFieldsType<T extends z.ZodType> = ReturnType<typeof baseDataFieldsSchema<T>>;
export type BaseDataFields<T> = z.infer<BaseDataFieldsType<z.ZodType<T>>>;

export class BaseData<T extends object> {
  id: string;
  table_info: TableInfo;
  created_at: string;
  updated_at: string;
  data: T;

  constructor(obj: BaseDataFields<T>) {
    refDataFieldsSchema.parse(obj);
    this.id = obj.id;
    this.table_info = obj.table_info;
    this.created_at = obj.created_at;
    this.updated_at = obj.updated_at;
    this.data = obj.data as T;
  }

  static nonFeaturesFields(): string[] {
    return ["id", "created_at", "updated_at"];
  }

  getDynamicFields(): string[] {
    const instanceKeys = Object.keys(this.data);
    return instanceKeys.filter(
      (key) => !(this.constructor as typeof BaseData).nonFeaturesFields().includes(key),
    );
  }
}

////////// BROWSER /////////////

const datasetStatSchema = z
  .object({
    name: z.string(),
    type: z.string(),
    histogram: z.array(z.record(z.string(), z.union([z.number(), z.string(), z.boolean()]))),
    range: z.optional(z.array(z.number())),
  })
  .strict();
export type DatasetStat = z.infer<typeof datasetStatSchema>;

const tableRowSchema = z.record(
  z.string(),
  z.union([z.string(), z.number(), z.boolean(), datasetStatSchema]),
);
export type TableRow = z.infer<typeof tableRowSchema>;

const tableColumnSchema = z
  .object({
    name: z.string(),
    type: z.string(),
  })
  .strict();
export type TableColumn = z.infer<typeof tableColumnSchema>;

const tableDataSchema = z
  .object({
    columns: z.array(tableColumnSchema),
    rows: z.array(tableRowSchema),
  })
  .strict();
export type TableData = z.infer<typeof tableDataSchema>;

const paginationInfoSchema = z
  .object({
    current_page: z.number(),
    page_size: z.number(),
    total_size: z.number(),
  })
  .strict();
export type PaginationInfo = z.infer<typeof paginationInfoSchema>;

const datasetBrowserSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    table_data: tableDataSchema,
    pagination: paginationInfoSchema,
    semantic_search: z.array(z.string()),
    isErrored: z.optional(z.boolean()),
  })
  .strict();
export type DatasetBrowserType = z.infer<typeof datasetBrowserSchema>;

export class DatasetBrowser implements DatasetBrowserType {
  id: string;
  name: string;
  table_data: TableData;
  pagination: PaginationInfo;
  semantic_search: Array<string>;
  isErrored?: boolean;

  constructor(obj: DatasetBrowserType) {
    datasetBrowserSchema.parse(obj);
    this.id = obj.id;
    this.name = obj.name;
    this.table_data = obj.table_data;
    this.pagination = obj.pagination;
    this.semantic_search = obj.semantic_search;
    this.isErrored = obj.isErrored;
  }
}

// DATASET

export interface FieldInfo {
  type: string;
  collection: boolean;
}
export interface DS_Schema {
  base_schema: BaseSchema;
  fields: Record<string, FieldInfo>;
  schema: string;
}

export type DS_NamedSchema = DS_Schema & {
  name: string;
};
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

export interface Dataset {
  id: string;
  path: string;
  previews_path: string;
  media_dir: string;
  thumbnail: string;
  dataset_schema: DatasetSchema;
  features_values: object; //not used right now, maybe we will make a real type if needed
  info: DatasetInfo;
}

export interface DatasetItems {
  items: Array<DatasetItem>;
  total: number;
}

// ITEM DATA

export type HTMLImage = {
  id: string;
  element: HTMLImageElement;
};
export type ImagesPerView = Record<string, HTMLImage[]>;

// ITEM OBJECT
export interface DisplayControl {
  hidden?: boolean;
  editing?: boolean;
}

export interface ObjectThumbnail {
  uri: string;
  baseImageDimensions: {
    width: number;
    height: number;
  };
  coords: Array<number>;
}

export type TrackletItem = {
  frame_index: number;
  tracklet_id: string;
  is_key?: boolean;
  is_thumbnail?: boolean;
  hidden?: boolean;
};

export type Schema = Annotation | Entity | Item | Source;

export type SaveItem = {
  change_type: "add" | "update" | "delete";
  object: Annotation | Entity | Item | Source;
};

// ITEM EMBEDDING
export interface ItemEmbedding {
  view_id: string;
  data: string;
}

// ITEM FEATURE

export interface ImageFeature {
  id: string;
  type: string;
  thumbnail: string; //string???? should be some of ItemFeature.value types
}

export interface ItemFeature {
  name: string;
  dtype: string;
  value: number | string | boolean | DatasetStat;
  required?: boolean;
}

export interface FeatureList {
  restricted: boolean;
  values: Array<string>;
}

export interface FeaturesValues {
  main: Record<string, FeatureList>;
  objects: Record<string, FeatureList>;
}

// UI DATA

export type MaskSVG = string[];

// LABELS DATA

export type ItemLabels = Record<string, SourceLabels>;

export interface SourceLabels {
  id: string;
  views: Record<string, ViewLabels>;
  numLabels: number;
  opened: boolean;
  visible: boolean;
}

export interface ViewLabels {
  id: string;
  categories: Record<string, CategoryLabels>;
  numLabels: number;
  opened: boolean;
  visible: boolean;
}

export interface CategoryLabels {
  id: number;
  name: string;
  labels: Record<string, Label>;
  opened: boolean;
  visible: boolean;
}

export interface Label {
  id: string;
  categoryId: number;
  categoryName: string;
  sourceId: string;
  viewRef: Reference;
  confidence?: number;
  bboxOpacity: number;
  maskOpacity: number;
  visible: boolean;
}
