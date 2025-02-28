/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

import { BaseSchema } from "../BaseSchema";
import type { BaseDataFields } from "../datasetTypes";
import { Image, type ImageType } from "./Image";
import { View, type ViewType } from "./View";

export const sequenceFrameSchema = z
  .object({
    timestamp: z.number(),
    frame_index: z.number(),
  })
  .passthrough();

export type SequenceFrameType = z.infer<typeof sequenceFrameSchema>; //export if needed

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

export const isSequenceFrameArray = (view: View | View[]): view is SequenceFrame[] =>
  Array.isArray(view) && view.every((v) => v.table_info.base_schema === BaseSchema.SequenceFrame);

// Defined here to avoid circular dependency
export const isMediaView = (view: View | View[]): view is Image | SequenceFrame[] => {
  if (Array.isArray(view)) {
    return view.every((v) => v.table_info.base_schema === BaseSchema.SequenceFrame);
  }
  return view.table_info.base_schema === BaseSchema.Image;
};
