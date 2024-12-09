import { z } from "zod";
import type { BaseDataFields } from "../datasetTypes";
import { type ImageType, Image } from "./Image";
import type { ViewType } from "./View";

const sequenceFrameSchema = z
  .object({
    timestamp: z.number(),
    frame_index: z.number(),
  })
  .passthrough();
export type SequenceFrameType = z.infer<typeof sequenceFrameSchema>; //export if needed

export class SequenceFrame extends Image {
  declare data: SequenceFrameType & ImageType & ViewType;

  constructor(obj: BaseDataFields<SequenceFrameType>) {
    if (obj.table_info.base_schema !== "SequenceFrame") throw new Error("Not a SequenceFrame");
    sequenceFrameSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<ImageType>);
    this.data = obj.data as SequenceFrameType & ImageType & ViewType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["timestamp", "frame_index"]);
  }
}
