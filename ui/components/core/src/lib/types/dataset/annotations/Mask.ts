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

export const maskSchema = z
  .object({
    size: z.array(z.number()).length(2),
    counts: z.array(z.number()).or(z.string()),
  })
  .passthrough();

export type MaskType = z.infer<typeof maskSchema>; //export if needed

export class Mask extends Annotation {
  declare data: MaskType & AnnotationType;

  //UI only fields
  ui: AnnotationUIFields & {
    opacity?: number;
    strokeFactor?: number;
    svg?: string[];
  } = {
    datasetItemType: WorkspaceType.UNDEFINED,
    displayControl: { hidden: false, editing: false },
  };

  constructor(obj: BaseDataFields<MaskType>) {
    if (obj.table_info.base_schema !== BaseSchema.Mask) throw new Error("Not a Mask");
    maskSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<AnnotationType>);
    this.data = obj.data as MaskType & AnnotationType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["size", "counts"]);
  }
}
