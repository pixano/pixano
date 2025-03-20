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

export const classificationSchema = z
  .object({
    labels: z.string().array(),
    confidences: z.number().array(),
  })
  .passthrough();

export type ClassificationType = z.infer<typeof classificationSchema>;

export class Classification extends Annotation {
  declare data: ClassificationType & AnnotationType;

  //UI only fields
  ui: AnnotationUIFields = {
    datasetItemType: WorkspaceType.UNDEFINED,
    displayControl: { hidden: false, editing: false },
  };

  constructor(obj: BaseDataFields<ClassificationType>) {
    if (obj.table_info.base_schema !== BaseSchema.Classification)
      throw new Error("Not a Classification");
    classificationSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<AnnotationType>);
    this.data = obj.data as ClassificationType & AnnotationType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["labels", "confidences"]);
  }
}
