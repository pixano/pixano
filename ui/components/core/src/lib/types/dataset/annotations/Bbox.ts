/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

import { BaseSchema } from "../BaseSchema";
import type { BaseDataFields } from "../datasetTypes";
import { WorkspaceType } from "../workspaceType";
import { Annotation, type AnnotationType, type AnnotationUIFields } from "./Annotation";

export const bboxSchema = z
  .object({
    confidence: z.number(),
    coords: z.array(z.number()).length(4),
    format: z.string(),
    is_normalized: z.boolean(),
  })
  .passthrough();

export type BBoxType = z.infer<typeof bboxSchema>;

export class BBox extends Annotation {
  declare data: BBoxType & AnnotationType;

  //UI only fields
  ui: AnnotationUIFields & {
    opacity?: number;
    strokeFactor?: number;
    tooltip?: string;
    startRef?: BBox; //for interpolated box
  } = {
    datasetItemType: WorkspaceType.UNDEFINED,
    displayControl: { hidden: false, editing: false },
  };

  constructor(obj: BaseDataFields<BBoxType>) {
    if (obj.table_info.base_schema !== BaseSchema.BBox) throw new Error("Not a BBox");
    bboxSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<AnnotationType>);
    this.data = obj.data as BBoxType & AnnotationType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["coords", "format", "is_normalized", "confidence"]);
  }
}
