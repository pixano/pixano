/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { createTypedAnnotation } from "$lib/utils/domainFactories";
import { createTypedEntity } from "$lib/utils/domainFactories";
import { createTypedView } from "$lib/utils/domainFactories";
// ─── BaseSchema ────────────────────────────────────────────────────────────────

export enum BaseSchema {
  BBox = "BBox",
  Mask = "CompressedRLE",
  Keypoints = "KeyPoints",
  Tracklet = "Tracklet",
  TextSpan = "TextSpan",
  Item = "Item",
  Track = "Track",
  Source = "Source",
  Entity = "Entity",
  Image = "Image",
  SequenceFrame = "SequenceFrame",
  TextView = "Text",
  Feature = "Feature",
  Classification = "Classification",
  Conversation = "Conversation",
  Message = "Message",
  MultiModalEntity = "MultiModalEntity",
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

// ─── Reference, TableInfo ──────────────────────────────────────────────────────

/** Mutable reference used in the existing persistence layer. See also document.ts Reference. */
export interface Reference {
  id: string;
  name: string;
}

/** Mutable table info used in the existing persistence layer. See also document.ts TableInfo. */
export interface TableInfo {
  name: string;
  group: string;
  base_schema: BaseSchema;
}

// ─── RawSchemaData ─────────────────────────────────────────────────────────────

export interface RawSchemaData {
  id: string;
  table_info: TableInfo;
  created_at: string;
  updated_at: string;
  data: Record<string, unknown>;
}

// ─── BaseData ──────────────────────────────────────────────────────────────────

export class BaseData<T extends object> {
  id: string;
  table_info: TableInfo;
  created_at: string;
  updated_at: string;
  data: T;

  constructor(obj: RawSchemaData) {
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

// ─── DatasetBrowser ────────────────────────────────────────────────────────────

export interface DatasetStat {
  name: string;
  type: string;
  histogram: Record<string, number | string | boolean>[];
  range?: number[];
}

export type TableRow = Record<string, string | number | boolean | DatasetStat>;

export interface TableColumn {
  name: string;
  type: string;
}

export interface TableData {
  columns: TableColumn[];
  rows: TableRow[];
}

export interface PaginationInfo {
  current_page: number;
  page_size: number;
  total_size: number;
}

export interface DatasetBrowserType {
  id: string;
  name: string;
  table_data: TableData;
  pagination: PaginationInfo;
  semantic_search: string[];
  isErrored?: boolean;
}

export class DatasetBrowser implements DatasetBrowserType {
  id: string;
  name: string;
  table_data: TableData;
  pagination: PaginationInfo;
  semantic_search: Array<string>;
  isErrored?: boolean;

  constructor(obj: DatasetBrowserType) {
    this.id = obj.id;
    this.name = obj.name;
    this.table_data = obj.table_data;
    this.pagination = obj.pagination;
    this.semantic_search = obj.semantic_search;
    this.isErrored = obj.isErrored;
  }
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

// ─── DisplayControl, AnnotationThumbnail, TrackletTimelineEntry ─────────────────────────────

export interface DisplayControl {
  hidden: boolean;
  editing: boolean;
  highlighted: "all" | "self" | "none";
  open?: boolean;
}

export const initDisplayControl: DisplayControl = {
  hidden: false,
  editing: false,
  highlighted: "all",
};

export interface AnnotationThumbnail {
  uri: string;
  view: string;
  baseImageDimensions: {
    width: number;
    height: number;
  };
  coords: Array<number>;
}

export type TrackletTimelineEntry = {
  frame_index: number;
  tracklet_id: string;
  is_key?: boolean;
  is_thumbnail?: boolean;
  hidden?: boolean;
};

// ─── Item Data Types ───────────────────────────────────────────────────────────

export type LoadedImage = {
  id: string;
  element: HTMLImageElement;
};
export type LoadedImagesPerView = Record<string, LoadedImage[]>;
export type ImagesPerView = LoadedImagesPerView;

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

export type MaskSvgPaths = string[];

// ─── DatasetInfo ───────────────────────────────────────────────────────────────

export interface DatasetInfoType {
  id: string;
  name: string;
  description: string;
  size: string;
  preview: string;
  workspace: string;
  num_items: number;
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
  isFiltered?: boolean;

  constructor(obj: DatasetInfoType) {
    this.id = obj.id;
    this.name = obj.name;
    this.description = obj.description;
    this.num_items = obj.num_items;
    this.size = obj.size;
    this.preview = obj.preview;
    this.workspace = obj.workspace as WorkspaceType;
    this.isFiltered = obj.isFiltered;
  }
}

// ─── Source ────────────────────────────────────────────────────────────────────

export interface SourceData {
  name: string;
  kind: string;
  metadata: Record<string, unknown>;
}

export class Source extends BaseData<SourceData> {
  constructor(obj: RawSchemaData) {
    super(obj);
  }
}

// ─── Item ──────────────────────────────────────────────────────────────────────

export class Item extends BaseData<Record<string, unknown>> {
  constructor(obj: RawSchemaData) {
    super(obj);
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields();
  }
}

// ─── Annotation ────────────────────────────────────────────────────────────────

export interface AnnotationData {
  item_ref: Reference;
  view_ref: Reference;
  entity_ref: Reference;
  source_ref: Reference;
  inference_metadata: Record<string, unknown>;
  [key: string]: unknown;
}

export type AnnotationUIFields = {
  datasetItemType: WorkspaceType;
  displayControl: DisplayControl;
  frame_index?: number;
  review_state?: "accepted" | "rejected"; //for pre-annotation
  top_entities?: Entity[];
};

export abstract class Annotation extends BaseData<AnnotationData> {
  //UI only fields
  ui: AnnotationUIFields = {
    datasetItemType: WorkspaceType.UNDEFINED,
    displayControl: initDisplayControl,
  };

  constructor(obj: RawSchemaData) {
    super(obj);
  }

  static nonFeaturesFields(): string[] {
    return super
      .nonFeaturesFields()
      .concat(["item_ref", "view_ref", "entity_ref", "source_ref", "inference_metadata"]);
  }

  static deepCreateInstanceArray(
    objs: Record<string, RawSchemaData[]>,
  ): Record<string, Annotation[]> {
    const newObj: Record<string, Annotation[]> = {};
    for (const [k, vs] of Object.entries(objs)) {
      newObj[k] = [];
      for (const v of vs) {
        const typedAnnotation = createTypedAnnotation(v as unknown as Annotation);
        if (typedAnnotation) {
          newObj[k].push(typedAnnotation);
        }
      }
    }
    return newObj;
  }

  is_type(type: BaseSchema): boolean {
    if (!this) {
      console.error("ERROR: do not use 'is_*' on uninitialized object");
      return false;
    }
    return this.table_info.base_schema === type;
  }
}

// ─── Entity ────────────────────────────────────────────────────────────────────

export interface EntityData {
  item_ref: Reference;
  view_ref: Reference;
  parent_ref: Reference;
  [key: string]: unknown;
}

export type EntityUIFields = {
  childs?: Annotation[];
  displayControl: DisplayControl;
};

export class Entity extends BaseData<EntityData> {
  //UI fields
  ui: EntityUIFields = { childs: [], displayControl: { ...initDisplayControl, open: false } };

  constructor(obj: RawSchemaData) {
    super(obj);
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["item_ref", "view_ref", "parent_ref"]);
  }

  static deepCreateInstanceArrayOrPlain(
    objs: Record<string, RawSchemaData | RawSchemaData[]>,
  ): Record<string, Entity[]> {
    const newObj: Record<string, Entity[]> = {};
    for (const [k, vs] of Object.entries(objs)) {
      newObj[k] = [];

      if (Array.isArray(vs)) {
        for (const v of vs) {
          newObj[k].push(createTypedEntity(v));
        }
      } else {
        newObj[k].push(createTypedEntity(vs));
      }
    }
    return newObj;
  }

  is_type(type: BaseSchema): boolean {
    if (!this) {
      console.error("ERROR: do not use 'is_*' on uninitialized object");
      return false;
    }
    return this.table_info.base_schema === type;
  }

  get is_track(): boolean {
    return this.is_type(BaseSchema.Track);
  }
  get is_conversation(): boolean {
    return this.is_type(BaseSchema.Conversation);
  }
}

// ─── BBox ──────────────────────────────────────────────────────────────────────

export interface BBoxData {
  confidence: number;
  coords: number[];
  format: string;
  is_normalized: boolean;
  [key: string]: unknown;
}

export class BBox extends Annotation {
  declare data: BBoxData & AnnotationData;

  //UI only fields
  ui: AnnotationUIFields & {
    opacity?: number;
    strokeFactor?: number;
    tooltip?: string;
    startRef?: BBox; //for interpolated box
  } = { datasetItemType: WorkspaceType.UNDEFINED, displayControl: initDisplayControl };

  constructor(obj: RawSchemaData) {
    super(obj);
    this.data = obj.data as BBoxData & AnnotationData;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["coords", "format", "is_normalized", "confidence"]);
  }
}

// ─── Classification ────────────────────────────────────────────────────────────

export interface ClassificationData {
  labels: string[];
  confidences: number[];
  [key: string]: unknown;
}

export class Classification extends Annotation {
  declare data: ClassificationData & AnnotationData;

  //UI only fields
  ui: AnnotationUIFields = {
    datasetItemType: WorkspaceType.UNDEFINED,
    displayControl: initDisplayControl,
  };

  constructor(obj: RawSchemaData) {
    super(obj);
    this.data = obj.data as ClassificationData & AnnotationData;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["labels", "confidences"]);
  }
}

// ─── Keypoints ─────────────────────────────────────────────────────────────────

export interface KeypointsData {
  template_id: string;
  coords: number[];
  states: string[];
  [key: string]: unknown;
}

export class Keypoints extends Annotation {
  declare data: KeypointsData & AnnotationData;

  //UI only fields
  ui: AnnotationUIFields & {
    opacity?: number;
    strokeFactor?: number;
    tooltip?: string;
  } = {
    datasetItemType: WorkspaceType.UNDEFINED,
    displayControl: initDisplayControl,
  };

  constructor(obj: RawSchemaData) {
    super(obj);
    this.data = obj.data as KeypointsData & AnnotationData;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["template_id", "coords", "states"]);
  }
}

// ─── Mask ──────────────────────────────────────────────────────────────────────

export interface MaskData {
  size: number[];
  counts: number[] | string;
  [key: string]: unknown;
}


export class Mask extends Annotation {
  declare data: MaskData & AnnotationData;

  //UI only fields
  ui: AnnotationUIFields & {
    opacity?: number;
    strokeFactor?: number;
    svg?: string[];
    tooltip?: string;
    rawPoints?: { x: number; y: number; id: number }[][];
  } = { datasetItemType: WorkspaceType.UNDEFINED, displayControl: initDisplayControl };

  constructor(obj: RawSchemaData) {
    super(obj);
    this.data = obj.data as MaskData & AnnotationData;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["size", "counts"]);
  }
}

// ─── TextSpan ──────────────────────────────────────────────────────────────────

export interface TextSpanData {
  spans_start: number[];
  spans_end: number[];
  mention: string;
  [key: string]: unknown;
}

export type TextSpanTypeWithViewRef = TextSpanData & {
  view_ref: Reference;
};

export class TextSpan extends Annotation {
  declare data: TextSpanData & AnnotationData;

  //UI only fields
  ui: AnnotationUIFields & {
    bgColor?: string;
  } = {
    datasetItemType: WorkspaceType.IMAGE_TEXT_ENTITY_LINKING,
    displayControl: initDisplayControl,
  };

  constructor(obj: RawSchemaData) {
    super(obj);
    this.data = obj.data as TextSpanData & AnnotationData;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["mention", "spans_start", "spans_end"]);
  }
}

// ─── Tracklet ──────────────────────────────────────────────────────────────────

export interface TrackletData {
  start_timestep: number;
  end_timestep: number;
  start_timestamp: number;
  end_timestamp: number;
  [key: string]: unknown;
}

export class Tracklet extends Annotation {
  declare data: TrackletData & AnnotationData;

  //UI only fields
  ui: AnnotationUIFields & {
    childs: Annotation[];
  } = { datasetItemType: WorkspaceType.VIDEO, childs: [], displayControl: initDisplayControl };

  constructor(obj: RawSchemaData) {
    super(obj);
    this.data = obj.data as TrackletData & AnnotationData;
  }

  static nonFeaturesFields(): string[] {
    return super
      .nonFeaturesFields()
      .concat(["start_timestep", "end_timestep", "start_timestamp", "end_timestamp"]);
  }
}

// ─── Message ───────────────────────────────────────────────────────────────────

export enum MessageTypeEnum {
  SYSTEM = "SYSTEM",
  QUESTION = "QUESTION",
  ANSWER = "ANSWER",
}

export enum QuestionTypeEnum {
  OPEN = "OPEN",
  SINGLE_CHOICE = "SINGLE_CHOICE",
  SINGLE_CHOICE_EXPLANATION = "SINGLE_CHOICE_EXPLANATION",
  MULTI_CHOICE = "MULTI_CHOICE",
  MULTI_CHOICE_EXPLANATION = "MULTI_CHOICE_EXPLANATION",
}

interface BaseMessageData {
  number: number;
  user: string;
  timestamp: string;
  content: string;
  [key: string]: unknown;
}

export type QuestionType = BaseMessageData & {
  type: MessageTypeEnum.QUESTION;
  choices: string[];
  question_type: QuestionTypeEnum;
};

export type AnswerType = BaseMessageData & {
  type: MessageTypeEnum.ANSWER;
};

export type SystemMessageType = BaseMessageData & {
  type: MessageTypeEnum.SYSTEM;
};

export type MessageType = QuestionType | AnswerType | SystemMessageType;

export class Message extends Annotation {
  declare data: MessageType & AnnotationData;

  //UI only fields
  ui: AnnotationUIFields = {
    datasetItemType: WorkspaceType.IMAGE_VQA,
    displayControl: initDisplayControl,
  };

  constructor(obj: RawSchemaData) {
    super(obj);
    this.data = obj.data as MessageType & AnnotationData;
  }

  static nonFeaturesFields(): string[] {
    return super
      .nonFeaturesFields()
      .concat([
        "number",
        "user",
        "type",
        "content",
        "timestamp",
        "choices",
        "question_type",
        "explanation",
      ]);
  }
}

export const isQuestionData = (messageType: MessageType): messageType is QuestionType => {
  return messageType.type === MessageTypeEnum.QUESTION;
};

// ─── View ──────────────────────────────────────────────────────────────────────

export interface ViewData {
  item_ref: Reference;
  parent_ref: Reference;
  [key: string]: unknown;
}

export abstract class View extends BaseData<ViewData> {
  constructor(obj: RawSchemaData) {
    super(obj);
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["item_ref", "parent_ref"]);
  }

  static deepCreateInstanceArrayOrPlain(
    objs: Record<string, RawSchemaData | RawSchemaData[]>,
  ): Record<string, View | View[]> {
    const newObj: Record<string, View | View[]> = {};
    for (const [k, vs] of Object.entries(objs)) {
      const view = createTypedView(vs as RawSchemaData | RawSchemaData[]);
      newObj[k] = view;
    }
    return newObj;
  }
}

// ─── Image ─────────────────────────────────────────────────────────────────────

export interface ImageData {
  url: string;
  width: number;
  height: number;
  format: string;
  [key: string]: unknown;
}

export class Image extends View {
  declare data: ImageData & ViewData;

  constructor(obj: RawSchemaData) {
    super(obj);
    this.data = obj.data as ImageData & ViewData;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["url"]);
  }
}

export const isImage = (view: View | View[]): view is Image =>
  Array.isArray(view) === false && view.table_info.base_schema === BaseSchema.Image;

// ─── SequenceFrame ─────────────────────────────────────────────────────────────

export interface SequenceFrameData {
  timestamp: number;
  frame_index: number;
  [key: string]: unknown;
}

export class SequenceFrame extends Image {
  declare data: SequenceFrameData & ImageData & ViewData;

  constructor(obj: RawSchemaData) {
    super(obj);
    this.data = obj.data as SequenceFrameData & ImageData & ViewData;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["timestamp", "frame_index"]);
  }
}

export const isSequenceFrameArray = (view: View | View[]): view is SequenceFrame[] =>
  Array.isArray(view) && view.every((v) => v.table_info.base_schema === BaseSchema.SequenceFrame);

// Defined here to avoid circular dependency
export const isMediaView = (view: View | View[]): view is Image | SequenceFrame[] => {
  if (Array.isArray(view)) {
    return view.every((v) => v.table_info.base_schema === BaseSchema.SequenceFrame);
  }
  return view.table_info.base_schema === BaseSchema.Image;
};

// ─── TextView ──────────────────────────────────────────────────────────────────

export interface TextViewData {
  content: string;
  [key: string]: unknown;
}

export class TextView extends View {
  declare data: TextViewData & ViewData;

  constructor(obj: RawSchemaData) {
    super(obj);
    this.data = obj.data as TextViewData & ViewData;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["content"]);
  }
}

export const isTextView = (view: View | View[]): view is TextView =>
  Array.isArray(view) === false && view.table_info.base_schema === BaseSchema.TextView;

// ─── ViewEmbedding ─────────────────────────────────────────────────────────────

export interface ViewEmbedding {
  id: string;
  table_info: TableInfo;
  created_at: string;
  updated_at: string;
  data: {
    item_ref: Reference;
    view_ref: Reference;
    vector: number[];
    shape: number[];
    [key: string]: unknown;
  };
}

// ─── DatasetItem ───────────────────────────────────────────────────────────────

export interface DatasetItemType {
  item: RawSchemaData;
  entities: Record<string, RawSchemaData | RawSchemaData[]>;
  annotations: Record<string, RawSchemaData[]>;
  views: Record<string, RawSchemaData | RawSchemaData[]>;
}

export class DatasetItem implements DatasetItemType {
  item: Item;
  entities: Record<string, Entity[]>;
  annotations: Record<string, Annotation[]>;
  views: Record<string, View | View[]>;

  //UI only fields
  ui: {
    datasetId: string;
    type: WorkspaceType;
  } = { datasetId: "", type: WorkspaceType.UNDEFINED };

  constructor(obj: DatasetItemType) {
    this.item = new Item(obj.item);
    this.entities = Entity.deepCreateInstanceArrayOrPlain(obj.entities);
    this.annotations = Annotation.deepCreateInstanceArray(obj.annotations);
    this.views = View.deepCreateInstanceArrayOrPlain(obj.views);
  }
}

// ─── DatasetMoreInfo ───────────────────────────────────────────────────────────

export interface DatasetMoreInfo {
  id: string;
  data: {
    source: string;
    split: string;
  };
  info: {
    annotations: Record<string, { count: number }>;
    entities: Record<string, { count: number }>;
    views: Record<string, { count: number }>;
    embeddings: Record<string, { count: number }>;
  };
  table_info: TableInfo;
}

// ─── Schema, SaveItem, DatasetItems, Dataset ───────────────────────────────────

export type Schema = Annotation | Entity | Item | Source;

/** Concrete save item for persistence — data is typed to Schema. See also services.ts SaveItem. */
export type SaveItem = {
  change_type: "add" | "update" | "delete";
  data: Schema;
};

export interface DatasetItems {
  items: Array<DatasetItem>;
  total: number;
}

export interface Dataset {
  id: string;
  path: string;
  previews_path: string;
  media_dir: string;
  thumbnail: string;
  dataset_schema: DatasetSchema;
  feature_values: object; //not used right now, maybe we will make a real type if needed
  info: DatasetInfo;
}
