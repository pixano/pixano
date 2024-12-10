/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import { BaseSchema } from "../BaseSchema";
import type { BaseDataFields } from "../datasetTypes";
import { View, type ViewType } from "./View";

const imageSchema = z
  .object({
    url: z.string(),
    width: z.number(),
    height: z.number(),
    format: z.string(),
  })
  .passthrough();

const sequenceFrameSchema = z
  .object({
    timestamp: z.number(),
    frame_index: z.number(),
  })
  .passthrough();

export type ImageType = z.infer<typeof imageSchema>; //export if needed
export type SequenceFrameType = z.infer<typeof sequenceFrameSchema>; //export if needed

export class Image extends View {
  declare data: ImageType & ViewType;

  constructor(obj: BaseDataFields<ImageType>) {
    // an Image can be a SequenceFrame
    if (![BaseSchema.Image, BaseSchema.SequenceFrame].includes(obj.table_info.base_schema))
      throw new Error("Not an Image");
    imageSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<ViewType>);
    this.data = obj.data as ImageType & ViewType;
  }

  static nonFeaturesFields(): string[] {
    //return super.nonFeaturesFields().concat(["url", "width", "height", "format"]);
    return super.nonFeaturesFields().concat(["url"]);
  }
}

export class SequenceFrame extends Image {
  declare data: SequenceFrameType & ImageType & ViewType;

  constructor(obj: BaseDataFields<SequenceFrameType>) {
    if (obj.table_info.base_schema !== BaseSchema.SequenceFrame)
      throw new Error("Not a SequenceFrame");
    sequenceFrameSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<ImageType>);
    this.data = obj.data as SequenceFrameType & ImageType & ViewType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["timestamp", "frame_index"]);
  }
}
