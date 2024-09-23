/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

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

const baseDataFieldsSchema = z
  .object({
    id: z.string(),
    table_info: tableInfoSchema,
    data: z.any(),
  })
  .strict();
type BaseDataFields = z.infer<typeof baseDataFieldsSchema>;

class BaseData implements BaseDataFields {
  id: string;
  table_info: TableInfo;
  data: Record<string, unknown>;

  constructor(obj: BaseDataFields) {
    baseDataFieldsSchema.parse(obj);
    this.id = obj.id;
    this.table_info = obj.table_info;
    this.data = obj.data as Record<string, unknown>;
  }
}
const zDataSchema = (kind: z.AnyZodObject) => {
  return z
    .object({
      id: z.string(),
      table_info: tableInfoSchema,
      data: kind,
    })
    .strict();
};

const viewSchema = z
  .object({
    item_ref: referenceSchema,
    parent_ref: referenceSchema,
  })
  .passthrough();
//type ViewType = z.infer<typeof viewSchema>;  //export if needed

export class View extends BaseData {
  constructor(obj: BaseDataFields) {
    viewSchema.parse(obj.data);
    super(obj);
  }
  static createInstance(obj: BaseDataFields) {
    if (obj.table_info.base_schema === "Image") return new Image(obj);
    if (obj.table_info.base_schema === "SequenceFrame")
      return new SequenceFrame(obj);
    return new View(obj);
  }

  static deepCreateInstanceArrayOrPlain(
    objs: Record<string, BaseDataFields | BaseDataFields[]>
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
//type ImageType = z.infer<typeof imageSchema>;  //export if needed
export class Image extends View {
  constructor(obj: BaseDataFields) {
    // an Image can be a SequenceFrame
    if (!["Image", "SequenceFrame"].includes(obj.table_info.base_schema))
      throw new Error("Not an Image");
    imageSchema.parse(obj.data);
    super(obj);
  }
}

const sequenceFrameSchema = z
  .object({
    timestamp: z.number(),
    frame_index: z.number(),
  })
  .passthrough();
//type SequenceFrameType = z.infer<typeof sequenceFrameSchema>;  //export if needed
export class SequenceFrame extends Image {
  constructor(obj: BaseDataFields) {
    if (obj.table_info.base_schema !== "SequenceFrame")
      throw new Error("Not a SequenceFrame");
    sequenceFrameSchema.parse(obj.data);
    super(obj);
  }
}

const entitySchema = z
  .object({
    item_ref: referenceSchema,
    view_ref: referenceSchema,
    parent_ref: referenceSchema,
  })
  .passthrough();
//type EntityType = z.infer<typeof entitySchema>;  //export if needed

export class Entity extends BaseData {
  constructor(obj: BaseDataFields) {
    entitySchema.parse(obj.data);
    super(obj);
  }

  static createInstance(obj: BaseDataFields) {
    if (obj.table_info.base_schema === "Track") return new Track(obj);
    return new Entity(obj);
  }

  static deepCreateInstanceArray(
    objs: Record<string, BaseDataFields[]>
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
//type TrackType = z.infer<typeof trackSchema>;  //export if needed

export class Track extends Entity {
  constructor(obj: BaseDataFields) {
    trackSchema.parse(obj.data);
    super(obj);
  }
}

const annotationSchema = z
  .object({
    item_ref: referenceSchema,
    view_ref: referenceSchema,
    entity_ref: referenceSchema,
  })
  .passthrough();
//type AnnotationType = z.infer<typeof annotationSchema>;  //export if needed

export class Annotation extends BaseData {
  constructor(obj: BaseDataFields) {
    annotationSchema.parse(obj.data);
    super(obj);
  }

  static createInstance(obj: BaseDataFields) {
    if (obj.table_info.base_schema === "BBox") return new BBox(obj);
    if (obj.table_info.base_schema === "Keypoints") return new Keypoints(obj);
    return new Annotation(obj);
  }

  static deepCreateInstanceArray(
    objs: Record<string, BaseDataFields[]>
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
}

const bboxSchema = z
  .object({
    confidence: z.number(),
    coords: z.array(z.number()).length(4),
    format: z.string(),
    is_normalized: z.boolean(),
  })
  .passthrough();
//type BBoxType = z.infer<typeof bboxSchema>;  //export if needed

export class BBox extends Annotation {
  constructor(obj: BaseDataFields) {
    if (obj.table_info.base_schema !== "BBox") throw new Error("Not a BBox");
    bboxSchema.parse(obj.data);
    super(obj);
  }
}

const keypointsSchema = z
  .object({
    template_id: z.string(),
    coords: z.array(z.number()),
    states: z.array(z.string()),
  })
  .passthrough();
//type KeypointsType = z.infer<typeof keypointsSchema>;  //export if needed

export class Keypoints extends Annotation {
  constructor(obj: BaseDataFields) {
    if (obj.table_info.base_schema !== "Keypoints")
      throw new Error("Not a Keypoints");
    keypointsSchema.parse(obj.data);
    super(obj);
  }
}

export class Item extends BaseData {
  constructor(obj: BaseDataFields) {
    if (obj.table_info.base_schema !== "Item") throw new Error("Not an Item");
    super(obj);
  }
}

const datasetInfoSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    description: z.string(),
    num_elements: z.optional(z.number()), // optional or remove ?
    size: z.string(),
    preview: z.string(),
    isFiltered: z.optional(z.boolean()),
  })
  .strict();
export type DatasetInfoType = z.infer<typeof datasetInfoSchema>;

export class DatasetInfo implements DatasetInfoType {
  id: string;
  name: string;
  description: string;
  num_elements?: number;
  size: string;
  preview: string;
  isFiltered?: boolean;

  constructor(obj: DatasetInfoType) {
    datasetInfoSchema.parse(obj);
    this.id = obj.id;
    this.name = obj.name;
    this.description = obj.description;
    this.num_elements = obj.num_elements;
    this.size = obj.size;
    this.preview = obj.preview;
    this.isFiltered = obj.isFiltered;
  }
}

const datasetStatSchema = z
  .object({
    name: z.string(),
    type: z.string(),
    histogram: z.array(
      z.record(z.string(), z.union([z.number(), z.string(), z.boolean()]))
    ),
    range: z.optional(z.array(z.number())),
  })
  .strict();
export type DatasetStat = z.infer<typeof datasetStatSchema>;

const tableRowSchema = z.record(
  z.string(),
  z.union([z.string(), z.number(), z.boolean(), datasetStatSchema])
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
  item: baseDataFieldsSchema, //we could make a type schema for Item, but it's the same...
  entities: z.record(z.string(), z.array(zDataSchema(entitySchema))),
  annotations: z.record(z.string(), z.array(zDataSchema(annotationSchema))),
  views: z.record(
    z.string(),
    zDataSchema(viewSchema).or(z.array(zDataSchema(viewSchema)))
  ),
}); //passthrough cause a compile error... may be an issue for UI fields
export type DatasetItemType = z.infer<typeof datasetItemSchema>;

export class DatasetItem implements DatasetItemType {
  id: string;
  item: Item;
  entities: Record<string, Entity[]>;
  annotations: Record<string, Annotation[]>;
  views: Record<string, View | View[]>;

  constructor(obj: DatasetItemType) {
    console.log("I'm Here!!");
    datasetItemSchema.parse(obj);
    this.id = obj.id;
    this.item = new Item(obj.item);

    this.entities = Entity.deepCreateInstanceArray(obj.entities);
    this.annotations = Annotation.deepCreateInstanceArray(obj.annotations);
    this.views = View.deepCreateInstanceArrayOrPlain(obj.views);
  }
}

//-------------OLD
//import type { Keypoints } from "./objectTypes";

// Exports

// DATASET

export interface Dataset {
  id: string;
  path: string;
  previews_path: string;
  media_dir: string;
  thumbnail: string;
  dataset_schema: {
    //not used right now, maybe we will make a real type if needed
    relations: object;
    schemas: object;
    group: object;
  };
  features_values: object; //not used right now, maybe we will make a real type if needed
  info: DatasetInfo;
}

// DATASET ITEM
// export interface DatasetItem {
//   id: string;
//   item: Item;
//   entities: Record<string, Entity[]>;
//   annotations: Record<string, Annotation[]>;
//   views: Record<string, View | View[]>;
// }

/////TMP WIP
//export type View = ItemView;
export type BaseDatasetItem = DatasetItem;
//////
//export type DatasetItem = ImageDatasetItem | VideoDatasetItem | ThreeDimensionsDatasetItem;

// type AnnotationBase = {
//   item_ref: Reference;
//   view_ref: Reference;
//   entity_ref: Reference;
// };

// type BBoxBase = AnnotationBase & {
//   coords: Array<number>;
//   format: string;
//   is_normalized: boolean;
//   confidence: number;
// };

// type KeypointsBase = AnnotationBase & {
//   template_id: string;
//   coords: Array<number>;
//   states: Array<string>;
// };

// type MaskBase = AnnotationBase & {
//   size: Array<number>;
//   counts: ArrayBuffer; //TODO : need testing
// };

// export type BBox = BaseSchemaModel<BBoxBase & Record<string, Any>>;
// export type Mask = BaseSchemaModel<MaskBase & Record<string, Any>>;
// export type Keypoints = BaseSchemaModel<KeypointsBase & Record<string, Any>>;
// export type Annotation = BBox | Keypoints | Mask;

// type EntityBase = {
//   item_ref: Reference;
//   view_ref: Reference;
//   parent_ref: Reference;
// };

// type TrackBase = EntityBase & {
//   name: string;
// };

// export type Track = BaseSchemaModel<TrackBase>;
// export type Entity = BaseSchemaModel<EntityBase> | Track;

export type ImageDatasetItem = BaseDatasetItem & {
  type: "image";
  // annotations: Record<string, ImageObject[]>;
  // entities: Record<string, ImageObject[]>;
  views: Record<string, View>;
};

export type VideoDatasetItem = BaseDatasetItem & {
  type: "video";
  // annotations: Record<string, VideoObject[]>;
  // entities: Record<string, VideoObject[]>;
  views: Record<string, View[]>;
};

export type ThreeDimensionsDatasetItem = BaseDatasetItem & {
  type: "3d";
  views: Record<string, View[]>;
};

export type DatasetItemSave = {
  id: string;
  split: string;
  item_features: Record<string, ItemFeature>;
  save_data: SaveItem[];
};

export interface DatasetItems {
  items: Array<DatasetItem>;
  total: number;
}

export interface TableInfo {
  name: string;
  group: string;
  base_schema: string;
}

// ITEM DATA

export interface ItemView {
  id: string;
  data: {
    type: string;
    url: string;
    item_ref: Reference;
    parent_ref: Reference;
    format: string;
    height: number;
    width: number;
    thumbnail?: string;
    frame_index?: number;
    total_frames?: number;
    features: Record<string, ItemFeature>;
  };
  table_info: TableInfo;
}

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

export type ItemObjectBase = {
  id: string;
  item_id: string;
  source_id: string;
  features: Record<string, ItemFeature>;
  data: Any;
  table_info: TableInfo;
  displayControl?: DisplayControl;
  highlighted?: "none" | "self" | "all";
  review_state?: "accepted" | "rejected";
};

export type TrackletItem = {
  frame_index: number;
  tracklet_id: string;
  is_key?: boolean;
  is_thumbnail?: boolean;
  hidden?: boolean;
};

export type SaveDataAddUpdate =
  | ItemBBox
  | VideoItemBBox
  | Keypoints
  | VideoKeypoints
  | ItemRLE
  | Tracklet
  | ItemObjectBase;

export interface SaveItemAddUpdate {
  change_type: "add_or_update";
  ref_name: string;
  is_video: boolean;
  data: SaveDataAddUpdate & {
    entity_ref?: Record<string, string>;
  };
}

export interface SaveItemDelete {
  change_type: "delete";
  ref_name: string;
  is_video: boolean;
  data: Record<string, string[]> & {
    entity_ref?: Record<string, string>;
  };
}

export type SaveItem = SaveItemAddUpdate | SaveItemDelete;

export type VideoItemBBox = ItemBBox & TrackletItem;
export type VideoKeypoints = Keypoints & TrackletItem;
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
  keypoints?: VideoKeypoints[];
  displayedMBox?: VideoItemBBox[]; //list for multiview
  displayedMKeypoints?: VideoKeypoints[]; //list for multiview
};

export type ImageObject = ItemObjectBase & {
  datasetItemType: "image";
  bbox?: ItemBBox;
  mask?: ItemRLE;
  keypoints?: Keypoints;
};

export type ItemObject = ImageObject | VideoObject;

export interface ItemRLE {
  id: string;
  ref_name: string;
  view_id?: string;
  counts: Array<number>;
  size: Array<number>;
  displayControl?: DisplayControl;
}

export interface ItemBBox {
  id: string;
  ref_name: string;
  view_id?: string;
  coords: Array<number>;
  format: string;
  is_normalized: boolean;
  confidence: number;
  displayControl?: DisplayControl;
}

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

export interface Mask {
  id: string;
  viewId: string;
  svg: MaskSVG;
  rle?: ItemRLE;
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
//   viewId: string;
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
  viewId: string;
  confidence?: number;
  bboxOpacity: number;
  maskOpacity: number;
  visible: boolean;
}
