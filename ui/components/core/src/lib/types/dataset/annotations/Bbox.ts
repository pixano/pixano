import { z } from "zod";
import type { BaseDataFields } from "../datasetTypes";
import { Annotation, type AnnotationType, type AnnotationUIFields } from "./Annotation";
import { AnnotationBaseSchema } from "./AnnotationBaseSchema";

const bboxSchema = z
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
  } = { datasetItemType: "" };

  constructor(obj: BaseDataFields<BBoxType>) {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-enum-comparison
    if (obj.table_info.base_schema !== AnnotationBaseSchema.BBox) throw new Error("Not a BBox");
    bboxSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<AnnotationType>);
    this.data = obj.data as BBoxType & AnnotationType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["coords", "format", "is_normalized", "confidence"]);
  }
}
