/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

import { BaseSchema } from "../BaseSchema";
import { referenceSchema, type BaseDataFields } from "../datasetTypes";
import { WorkspaceType } from "../workspaceType";
import { Annotation, type AnnotationType, type AnnotationUIFields } from "./Annotation";

export const textSpanSchema = z
  .object({
    spans_start: z.number().array(),
    spans_end: z.number().array(),
    mention: z.string(),
    annotation_ref: referenceSchema,
  })
  .passthrough();

export type TextSpanType = z.infer<typeof textSpanSchema>;

export class TextSpan extends Annotation {
  declare data: TextSpanType & AnnotationType;

  //UI only fields
  ui: AnnotationUIFields & {
    bgColor?: string;
  } = { datasetItemType: WorkspaceType.IMAGE_TEXT_ENTITY_LINKING };

  constructor(obj: BaseDataFields<TextSpanType>) {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-enum-comparison
    if (obj.table_info.base_schema !== BaseSchema.TextSpan) throw new Error("Not a TextSpan");
    textSpanSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<AnnotationType>);
    this.data = obj.data as TextSpanType & AnnotationType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["mention", "spans_start", "spans_end"]);
  }
}
