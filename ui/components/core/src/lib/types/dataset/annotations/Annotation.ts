import { z } from "zod";
import {
  BaseData,
  referenceSchema,
  type BaseDataFields,
  type DisplayControl,
} from "../datasetTypes";
import type { Entity } from "../entities";
import { BBox, type BBoxType } from "./Bbox";
import { Keypoints, type KeypointsType } from "./Keypoint";
import { Mask, type MaskType } from "./Mask";
import { Tracklet, type TrackletType } from "./Tracklet";

export const annotationSchema = z
  .object({
    item_ref: referenceSchema,
    view_ref: referenceSchema,
    entity_ref: referenceSchema,
    source_ref: referenceSchema,
  })
  .passthrough();
export type AnnotationType = z.infer<typeof annotationSchema>; //export if needed

export type AnnotationUIFields = {
  datasetItemType: string;
  //features: Record<string, ItemFeature>;
  displayControl?: DisplayControl;
  highlighted?: "none" | "self" | "all";
  frame_index?: number;
  review_state?: "accepted" | "rejected"; //for pre-annotation
  top_entities?: Entity[];
};

export class Annotation extends BaseData<AnnotationType> {
  //UI only fields
  ui: AnnotationUIFields = { datasetItemType: "" };

  constructor(obj: BaseDataFields<AnnotationType>) {
    annotationSchema.parse(obj.data);
    super(obj);
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["item_ref", "view_ref", "entity_ref", "source_ref"]);
  }

  static createInstance(obj: BaseDataFields<AnnotationType>) {
    if (obj.table_info.base_schema === "BBox")
      return new BBox(obj as unknown as BaseDataFields<BBoxType>);
    if (obj.table_info.base_schema === "KeyPoints")
      return new Keypoints(obj as unknown as BaseDataFields<KeypointsType>);
    if (obj.table_info.base_schema === "CompressedRLE")
      return new Mask(obj as unknown as BaseDataFields<MaskType>);
    if (obj.table_info.base_schema === "Tracklet")
      return new Tracklet(obj as unknown as BaseDataFields<TrackletType>);
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

  is_type(type: string): boolean {
    if (!this) {
      console.error("ERROR: do not use 'is_*' on uninitialized object");
      return false;
    }
    return this.table_info.base_schema === type;
  }
  get is_bbox(): boolean {
    return this.is_type("BBox");
  }
  get is_keypoints(): boolean {
    return this.is_type("KeyPoints");
  }
  get is_mask(): boolean {
    return this.is_type("CompressedRLE");
  }
  get is_tracklet(): boolean {
    return this.is_type("Tracklet");
  }
}
