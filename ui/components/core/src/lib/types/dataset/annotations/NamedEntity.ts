/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import type { BaseDataFields } from "../datasetTypes";
import { Annotation, type AnnotationType, type AnnotationUIFields } from "./Annotation";
import { BaseSchema } from "../BaseSchema";

export const namedEntitySchema = z
  .object({
    startIndex: z.number(),
    endIndex: z.number(),
    content: z.string(),
  })
  .passthrough();
export type NamedEntityType = z.infer<typeof namedEntitySchema>;

export class NamedEntity extends Annotation {
  declare data: NamedEntityType & AnnotationType;

  //UI only fields
  ui: AnnotationUIFields & {
    bgColor?: string;
  } = { datasetItemType: "text" };

  constructor(obj: BaseDataFields<NamedEntityType>) {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-enum-comparison
    if (obj.table_info.base_schema !== BaseSchema.NamedEntity) throw new Error("Not a NamedEntity");
    namedEntitySchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<AnnotationType>);
    this.data = obj.data as NamedEntityType & AnnotationType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["content", "startIndex", "endIndex"]);
  }
}