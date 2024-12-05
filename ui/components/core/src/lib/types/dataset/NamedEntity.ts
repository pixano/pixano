import { z } from "zod";
import {
  Annotation,
  type AnnotationType,
  type AnnotationUIFields,
  type BaseDataFields,
} from "../datasetTypes";

const NamedEntitySchema = z
  .object({
    content: z.string(),
  })
  .passthrough();
export type NamedEntityType = z.infer<typeof NamedEntitySchema>;

export class NamedEntity extends Annotation {
  declare data: NamedEntityType & AnnotationType;

  //UI only fields
  ui: AnnotationUIFields & {
    bgColor?: string;
  } = { datasetItemType: "text" };

  constructor(obj: BaseDataFields<NamedEntityType>) {
    // if (obj.table_info.base_schema !== "NamedEntity") throw new Error("Not a NamedEntity");
    NamedEntitySchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<AnnotationType>);
    this.data = obj.data as NamedEntityType & AnnotationType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["content"]);
  }
}
