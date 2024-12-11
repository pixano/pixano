/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import type { BaseDataFields } from "../datasetTypes";
import { Annotation, type AnnotationType, type AnnotationUIFields } from "./Annotation";
import { BaseSchema } from "../BaseSchema";

export const textSpanSchema = z
  .object({
    startIndex: z.number(),
    endIndex: z.number(),
    content: z.string(),
  })
  .passthrough();
export type TextSpanType = z.infer<typeof textSpanSchema>;

export class TextSpan extends Annotation {
  declare data: TextSpanType & AnnotationType;

  //UI only fields
  ui: AnnotationUIFields & {
    bgColor?: string;
  } = { datasetItemType: "text" };

  constructor(obj: BaseDataFields<TextSpanType>) {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-enum-comparison
    if (obj.table_info.base_schema !== BaseSchema.TextSpan) throw new Error("Not a TextSpan");
    textSpanSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<AnnotationType>);
    this.data = obj.data as TextSpanType & AnnotationType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["content", "startIndex", "endIndex"]);
  }
}
