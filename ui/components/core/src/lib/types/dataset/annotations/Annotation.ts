/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import { createTypedAnnotation } from "../../../utils/annotations";
import {
  BaseData,
  referenceSchema,
  type BaseDataFields,
  type DisplayControl,
} from "../datasetTypes";
import type { Entity } from "../entities";
import { AnnotationBaseSchema } from "./AnnotationBaseSchema";

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

export abstract class Annotation extends BaseData<AnnotationType> {
  //UI only fields
  ui: AnnotationUIFields = { datasetItemType: "" };

  constructor(obj: BaseDataFields<AnnotationType>) {
    annotationSchema.parse(obj.data);
    super(obj);
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["item_ref", "view_ref", "entity_ref", "source_ref"]);
  }

  static deepCreateInstanceArray(
    objs: Record<string, BaseDataFields<AnnotationType>[]>,
  ): Record<string, Annotation[]> {
    const newObj: Record<string, Annotation[]> = {};
    for (const [k, vs] of Object.entries(objs)) {
      newObj[k] = [];
      for (const v of vs) {
        const typedAnnotation = createTypedAnnotation(v as Annotation);
        if (typedAnnotation) {
          newObj[k].push(typedAnnotation);
        }
      }
    }
    return newObj;
  }

  is_type(type: AnnotationBaseSchema): boolean {
    if (!this) {
      console.error("ERROR: do not use 'is_*' on uninitialized object");
      return false;
    }
    // eslint-disable-next-line @typescript-eslint/no-unsafe-enum-comparison
    return this.table_info.base_schema === type;
  }

  get is_bbox(): boolean {
    return this.is_type(AnnotationBaseSchema.BBox);
  }
  get is_keypoints(): boolean {
    return this.is_type(AnnotationBaseSchema.Keypoints);
  }
  get is_mask(): boolean {
    return this.is_type(AnnotationBaseSchema.Mask);
  }
  get is_tracklet(): boolean {
    return this.is_type(AnnotationBaseSchema.Tracklet);
  }
  get is_named_entity(): boolean {
    return this.is_type(AnnotationBaseSchema.NamedEntity);
  }
}
