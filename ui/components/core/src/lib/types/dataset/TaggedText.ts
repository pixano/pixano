import { z } from "zod";
import { Annotation, type AnnotationType, type AnnotationUIFields, type BaseDataFields } from "../datasetTypes";

const taggedTextSchema = z
  .object({
    content: z.string(),
  })
  .passthrough();
export type TaggedTextType = z.infer<typeof taggedTextSchema>;

export class TaggedText extends Annotation {
  declare data: TaggedTextType & AnnotationType;

  //UI only fields
  ui: AnnotationUIFields & {
    bgColor?: string;
  } = { datasetItemType: "text" };

  constructor(obj: BaseDataFields<TaggedTextType>) {
    // if (obj.table_info.base_schema !== "TaggedText") throw new Error("Not a TaggedText");
    taggedTextSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<AnnotationType>);
    this.data = obj.data as TaggedTextType & AnnotationType;
  }

  static nonFeaturesFields(): string[] {
    return super
      .nonFeaturesFields()
      .concat(["content"]);
  }
}
