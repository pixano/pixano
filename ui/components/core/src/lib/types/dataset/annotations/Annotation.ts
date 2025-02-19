/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

import { createTypedAnnotation } from "../../../utils/annotations";
import { BaseSchema } from "../BaseSchema";
import {
  BaseData,
  referenceSchema,
  type BaseDataFields,
  type DisplayControl,
} from "../datasetTypes";
import type { Entity } from "../entities";
import { WorkspaceType } from "../workspaceType";

export const annotationSchema = z
  .object({
    item_ref: referenceSchema,
    view_ref: referenceSchema,
    entity_ref: referenceSchema,
    source_ref: referenceSchema,
    inference_metadata: z.record(z.any()),
  })
  .passthrough();

export type AnnotationType = z.infer<typeof annotationSchema>; //export if needed

export type AnnotationUIFields = {
  datasetItemType: WorkspaceType;
  //features: Record<string, ItemFeature>;
  displayControl?: DisplayControl;
  highlighted?: "none" | "self" | "all";
  frame_index?: number;
  review_state?: "accepted" | "rejected"; //for pre-annotation
  top_entities?: Entity[];
};

export abstract class Annotation extends BaseData<AnnotationType> {
  //UI only fields
  ui: AnnotationUIFields = { datasetItemType: WorkspaceType.UNDEFINED };

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

  is_type(type: BaseSchema): boolean {
    if (!this) {
      console.error("ERROR: do not use 'is_*' on uninitialized object");
      return false;
    }
    // eslint-disable-next-line @typescript-eslint/no-unsafe-enum-comparison
    return this.table_info.base_schema === type;
  }
}
