/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import type { ItemKeypoints } from "./objectTypes";

const referenceSchema = z
  .object({
    id: z.string(),
    name: z.string(),
  })
  .strict();
export type Reference = z.infer<typeof referenceSchema>;

const tableInfoSchema = z
  .object({
    name: z.string(),
    group: z.string(),
    base_schema: z.string(),
  })
  .strict();
export type TableInfo = z.infer<typeof tableInfoSchema>;

//note: this one is needed only to parse in BaseData<T> constructor
//because I can't find a way to parse with the generic typed version
const refDataFieldsSchema = z
  .object({
    id: z.string(),
    table_info: tableInfoSchema,
    created_at: z.string(),
    updated_at: z.string(),
    data: z.any(),
  })
  .strict();
const baseDataFieldsSchema = <T extends z.ZodType>(schema: T) => {
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
type BaseDataFields<T> = z.infer<BaseDataFieldsType<z.ZodType<T>>>;

class BaseData<T> {
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
    this.data = obj.data;
  }
}

const viewSchema = z
  .object({
    item_ref: referenceSchema,
    parent_ref: referenceSchema,
  })
  .passthrough();
type ViewType = z.infer<typeof viewSchema>; //export if needed

export class View extends BaseData<ViewType> {
  constructor(obj: BaseDataFields<ViewType>) {
    viewSchema.parse(obj.data);
    super(obj);
  }
  static createInstance(obj: BaseDataFields<ViewType>) {
    if (obj.table_info.base_schema === "Image") return new Image(obj);
    if (obj.table_info.base_schema === "SequenceFrame") return new SequenceFrame(obj);
    return new View(obj);
  }

  static deepCreateInstanceArrayOrPlain(
    objs: Record<string, BaseDataFields<ViewType> | BaseDataFields<ViewType>[]>,
  ): Record<string, View | View[]> {
    const newObj: Record<string, View | View[]> = {};
    for (const [k, vs] of Object.entries(objs)) {
      if (Array.isArray(vs)) {
        const temp = [];
        for (const v of vs) {
          temp.push(View.createInstance(v));
        }
        newObj[k] = temp;
      } else {
        newObj[k] = View.createInstance(vs);
      }
    }
    return newObj;
  }
}

const imageSchema = z
  .object({
    url: z.string(),
    width: z.number(),
    height: z.number(),
    format: z.string(),
  })
  .passthrough();
type ImageType = z.infer<typeof imageSchema>; //export if needed
export class Image extends View {
  data: ImageType & ViewType;

  constructor(obj: BaseDataFields<ImageType>) {
    // an Image can be a SequenceFrame
    if (!["Image", "SequenceFrame"].includes(obj.table_info.base_schema))
      throw new Error("Not an Image");
    imageSchema.parse(obj.data);
    super(obj);
    this.data = obj.data;
  }
}

const sequenceFrameSchema = z
  .object({
    timestamp: z.number(),
    frame_index: z.number(),
  })
  .passthrough();
type SequenceFrameType = z.infer<typeof sequenceFrameSchema>; //export if needed
export class SequenceFrame extends Image {
  data: SequenceFrameType & ImageType & ViewType;

  constructor(obj: BaseDataFields<SequenceFrameType>) {
    if (obj.table_info.base_schema !== "SequenceFrame") throw new Error("Not a SequenceFrame");
    sequenceFrameSchema.parse(obj.data);
    super(obj);
    this.data = obj.data;
  }
}

const entitySchema = z
  .object({
    item_ref: referenceSchema,
    view_ref: referenceSchema,
    parent_ref: referenceSchema,
  })
  .passthrough();
type EntityType = z.infer<typeof entitySchema>; //export if needed

export class Entity extends BaseData<EntityType> {
  constructor(obj: BaseDataFields<EntityType>) {
    entitySchema.parse(obj.data);
    super(obj);
  }

  static createInstance(obj: BaseDataFields<EntityType>) {
    if (obj.table_info.base_schema === "Track") return new Track(obj);
    return new Entity(obj);
  }

  static deepCreateInstanceArray(
    objs: Record<string, BaseDataFields<EntityType>[]>,
  ): Record<string, Entity[]> {
    const newObj: Record<string, Entity[]> = {};
    for (const [k, vs] of Object.entries(objs)) {
      newObj[k] = [];
      for (const v of vs) {
        newObj[k].push(Entity.createInstance(v));
      }
    }
    return newObj;
  }
}

const trackSchema = z
  .object({
    name: z.string(),
  })
  .passthrough();
type TrackType = z.infer<typeof trackSchema>; //export if needed

export class Track extends Entity {
  constructor(obj: BaseDataFields<TrackType>) {
    trackSchema.parse(obj.data);
    super(obj);
  }
}

const annotationSchema = z
  .object({
    item_ref: referenceSchema,
    view_ref: referenceSchema,
    entity_ref: referenceSchema,
    source_ref: referenceSchema,
  })
  .passthrough();
type AnnotationType = z.infer<typeof annotationSchema>; //export if needed
export class Annotation extends BaseData<AnnotationType> {
  //UI only fields
  datasetItemType: string;
  //features: Record<string, ItemFeature>;
  displayControl: DisplayControl;
  highlighted: "none" | "self" | "all";

  constructor(obj: BaseDataFields<AnnotationType>) {
    annotationSchema.parse(obj.data);
    super(obj);
  }

  static createInstance(obj: BaseDataFields<AnnotationType>) {
    if (obj.table_info.base_schema === "BBox") return new BBox(obj);
    if (obj.table_info.base_schema === "KeyPoints") return new Keypoints(obj);
    if (obj.table_info.base_schema === "CompressedRLE") return new Mask(obj);
    return new Annotation(obj);
  }

  static deepCreateInstanceArray(
    objs: Record<string, BaseDataFields<AnnotationType>[]>,
  ): Record<string, Annotation[]> {
    const newObj: Record<string, Annotation[]> = {};
    for (const [k, vs] of Object.entries(objs)) {
      newObj[k] = [];
      for (const v of vs) {
        newObj[k].push(Annotation.createInstance(v));
      }
    }
    return newObj;
  }

  get is_bbox(): boolean {
    return this.table_info.base_schema === "BBox";
  }
  get is_keypoints(): boolean {
    return this.table_info.base_schema === "KeyPoints";
  }
  get is_mask(): boolean {
    return this.table_info.base_schema === "CompressedRLE";
  }
}

const bboxSchema = z
  .object({
    confidence: z.number(),
    coords: z.array(z.number()).length(4),
    format: z.string(),
    is_normalized: z.boolean(),
  })
  .passthrough();
export type BBoxType = z.infer<typeof bboxSchema>;

export class BBox extends Annotation {
  data: BBoxType & AnnotationType;

  //UI only fields
  opacity?: number;
  visible?: boolean;
  editing?: boolean;
  strokeFactor?: number;
  tooltip?: string;

  constructor(obj: BaseDataFields<BBoxType>) {
    if (obj.table_info.base_schema !== "BBox") throw new Error("Not a BBox");
    bboxSchema.parse(obj.data);
    super(obj);
    this.data = obj.data;
  }
}

const keypointsSchema = z
  .object({
    template_id: z.string(),
    coords: z.array(z.number()),
    states: z.array(z.string()),
  })
  .passthrough();
type KeypointsType = z.infer<typeof keypointsSchema>; //export if needed

export class Keypoints extends Annotation {
  data: KeypointsType & AnnotationType;

  //UI only fields
  //opacity?: number;
  visible?: boolean;
  editing?: boolean;
  //strokeFactor?: number;

  constructor(obj: BaseDataFields<KeypointsType>) {
    if (obj.table_info.base_schema !== "KeyPoints") throw new Error("Not a Keypoints");
    keypointsSchema.parse(obj.data);
    super(obj);
    this.data = obj.data;
  }
}

const maskSchema = z
  .object({
    size: z.array(z.number()).length(2),
    counts: z.array(z.number()).or(z.string()),
  })
  .passthrough();
export type MaskType = z.infer<typeof maskSchema>; //export if needed

export class Mask extends Annotation {
  data: MaskType & AnnotationType;

  //UI only fields
  opacity?: number;
  visible?: boolean;
  editing?: boolean;
  strokeFactor?: number;
  svg: string[];
  catId?: number;  //really needed ??

  constructor(obj: BaseDataFields<MaskType>) {
    if (obj.table_info.base_schema !== "CompressedRLE") throw new Error("Not a Mask");
    maskSchema.parse(obj.data);
    super(obj);
    this.data = obj.data;
  }
}

const itemSchema = z.object({}).passthrough();
type ItemType = z.infer<typeof itemSchema>;

export class Item extends BaseData<ItemType> {
  constructor(obj: BaseDataFields<ItemType>) {
    if (obj.table_info.base_schema !== "Item") throw new Error("Not an Item");
    super(obj);
  }
}

const datasetInfoSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    description: z.string(),
    size: z.string(),
    preview: z.string(),
    num_items: z.number(),
    isFiltered: z.optional(z.boolean()),
  })
  .strict();
export type DatasetInfoType = z.infer<typeof datasetInfoSchema>;

export class DatasetInfo implements DatasetInfoType {
  id: string;
  name: string;
  description: string;
  num_items: number;
  size: string;
  preview: string;
  isFiltered?: boolean;

  constructor(obj: DatasetInfoType) {
    datasetInfoSchema.parse(obj);
    this.id = obj.id;
    this.name = obj.name;
    this.description = obj.description;
    this.num_items = obj.num_items;
    this.size = obj.size;
    this.preview = obj.preview;
    this.isFiltered = obj.isFiltered;
  }
}

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

// DATASET ITEM
const datasetItemSchema = z.object({
  id: z.string(),
  item: baseDataFieldsSchema(itemSchema), //we could make a type schema for Item, but it's the same...
  entities: z.record(z.string(), z.array(baseDataFieldsSchema(entitySchema))),
  annotations: z.record(z.string(), z.array(baseDataFieldsSchema(annotationSchema))),
  views: z.record(
    z.string(),
    baseDataFieldsSchema(viewSchema).or(z.array(baseDataFieldsSchema(viewSchema))),
  ),
});
export type DatasetItemType = z.infer<typeof datasetItemSchema>;

export class DatasetItem implements DatasetItemType {
  id: string;
  item: Item;
  entities: Record<string, Entity[]>;
  annotations: Record<string, Annotation[]>;
  views: Record<string, Image | SequenceFrame[]>;

  //UI only fields
  datasetId: string;
  type: string;

  constructor(obj: DatasetItemType) {
    datasetItemSchema.parse(obj);
    this.id = obj.id;
    this.item = new Item(obj.item);

    this.entities = Entity.deepCreateInstanceArray(obj.entities);
    this.annotations = Annotation.deepCreateInstanceArray(obj.annotations);
    this.views = View.deepCreateInstanceArrayOrPlain(obj.views);
  }
}

//-------------OLD & WIP

//////////WIP

export type ImageDatasetItem = DatasetItem & {
  type: "image";
  // annotations: Record<string, ImageObject[]>;
  // entities: Record<string, ImageObject[]>;
  views: Record<string, View>;
};

export type VideoDatasetItem = DatasetItem & {
  type: "video";
  // annotations: Record<string, VideoObject[]>;
  // entities: Record<string, VideoObject[]>;
  views: Record<string, View[]>;
};

export type ThreeDimensionsDatasetItem = DatasetItem & {
  type: "3d";
  views: Record<string, View[]>;
};

// DATASET

export interface FieldInfo {
  type: string;
  collection: boolean;
}
export interface DS_Schema {
  base_schema: string;
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

// export type DatasetItemSave = {
//   id: string;
//   split: string;
//   item_features: Record<string, ItemFeature>;
//   save_data: SaveItem[];
// };

export interface DatasetItems {
  items: Array<DatasetItem>;
  total: number;
}

// export interface TableInfo {
//   name: string;
//   group: string;
//   base_schema: string;
// }

// ITEM DATA

export interface Base {
  id: string;
  table_info: TableInfo;
  created_at: string;
  updated_at: string;
  data: object;
}

interface ViewData extends Base["data"] {
  type: string;
  url: string;
  parent_ref: Reference;
  format: string;
  height: number;
  width: number;
  thumbnail?: string;
  frame_index?: number;
  total_frames?: number;
  features: Record<string, ItemFeature>;
}

export type ItemView = Base & {
  data: ViewData;
};

export type HTMLImage = {
  id: string;
  element: HTMLImageElement
}
export type ImagesPerView = Record<string, HTMLImage[]>
// export interface ItemView {
//   id: string;
//   data: {
//     type: string;
//     url: string;
//     item_ref: Reference;
//     parent_ref: Reference;
//     format: string;
//     height: number;
//     width: number;
//     thumbnail?: string;
//     frame_index?: number;
//     total_frames?: number;
//     features: Record<string, ItemFeature>;
//   };
//   table_info: TableInfo;
// }

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

export interface ItemObjectBase extends Base["data"] {
  item_ref: Reference;
  entity_ref: Reference;
  source_ref: Reference; //here or only in ItemAnnotation?
  view_ref: Reference;
  item_id: string;
  //source_id: string;
  features: Record<string, ItemFeature>;
  displayControl?: DisplayControl;
  highlighted?: "none" | "self" | "all";
  review_state?: "accepted" | "rejected";
}

export type TrackletItem = {
  frame_index: number;
  tracklet_id: string;
  is_key?: boolean;
  is_thumbnail?: boolean;
  hidden?: boolean;
};

// export type SaveDataAddUpdate =
//   | BBox
//   | VideoItemBBox
//   | ItemKeypoints
//   | VideoItemKeypoints
//   | Mask
//   | Tracklet
//   | ItemObjectBase;

export type Schema = Annotation | Entity | Item | View;

interface SaveBase {
  object: Annotation | Entity | Item;
}
export type SaveAdd = SaveBase & {
  change_type: "add";
  kind: "annotations" | "items" | "entities";
};
export type SaveUpdate = SaveBase & {
  change_type: "update";
};
export type SaveDelete = SaveBase & {
  change_type: "delete";
};
export type SaveItem = SaveAdd | SaveUpdate | SaveDelete;

export type VideoItemBBox = BBox & TrackletItem;
export type VideoItemKeypoints = ItemKeypoints & TrackletItem;
export interface Tracklet {
  start: number;
  end: number;
  id: string;
  view_id: string;
}

export type TrackletWithItems = Tracklet & {
  items: TrackletItem[];
};

export type VideoObject = ItemObjectBase & {
  datasetItemType: "video";
  track: Tracklet[];
  boxes?: VideoItemBBox[];
  keypoints?: VideoItemKeypoints[];
  displayedMBox?: VideoItemBBox[]; //list for multiview
  displayedMKeypoints?: VideoItemKeypoints[]; //list for multiview
};

// export type ImageObject = ItemObjectBase & {
//   datasetItemType: "image";
//   // bbox?: ItemBBox;
//   // mask?: ItemRLE;
//   // keypoints?: ItemKeypoints;
// };

export type ImageObject = BBox | Mask | Keypoints;

//export type ItemObject = ImageObject | VideoObject;

// export interface ItemRLE {
//   id: string;
//   ref_name: string;
//   view_id?: string;
//   counts: Array<number>;
//   size: Array<number>;
//   displayControl?: DisplayControl;
// }

// export type ItemBBox = BBox;
// export interface ItemBBox {
//   id: string;
//   ref_name: string;
//   view_id: string;
//   coords: Array<number>;
//   format: string;
//   is_normalized: boolean;
//   confidence: number;
//   displayControl?: DisplayControl;
// }

// ITEM EMBEDDING
export interface ItemEmbedding {
  view_id: string;
  data: string;
}

// ITEM FEATURE

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

//not used anymore...
export interface CanvasMask {
  id: string;
  viewRef: Reference;
  svg: MaskSVG;
  rle?: MaskType;
  catId: number;
  visible: boolean;
  editing: boolean;
  opacity: number;
  coordinates?: number[];
  strokeFactor?: number;
  highlighted?: "none" | "self" | "all";
}

export type MaskSVG = string[];

// Need to be reworker vs back BBox
// export interface BBox {
//   id: string;
//   viewRef: Reference;
//   bbox: Array<number>; // should be rename - current coordinate
//   tooltip: string;
//   catId: number;
//   visible: boolean;
//   opacity: number;
//   editing?: boolean;
//   strokeFactor?: number;
//   highlighted?: "none" | "self" | "all";
// }

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
