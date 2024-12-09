import { z } from "zod";
import type { BaseDataFields } from "../datasetTypes";
import { Annotation, type AnnotationType, type AnnotationUIFields } from "./Annotation";

const keypointsSchema = z
  .object({
    template_id: z.string(),
    coords: z.array(z.number()),
    states: z.array(z.string()),
  })
  .passthrough();

export type KeypointsType = z.infer<typeof keypointsSchema>; //export if needed

export class Keypoints extends Annotation {
  declare data: KeypointsType & AnnotationType;

  //UI only fields
  ui: AnnotationUIFields = { datasetItemType: "" };

  constructor(obj: BaseDataFields<KeypointsType>) {
    if (obj.table_info.base_schema !== "KeyPoints") throw new Error("Not a Keypoints");
    keypointsSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<AnnotationType>);
    this.data = obj.data as KeypointsType & AnnotationType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["template_id", "coords", "states"]);
  }
}
