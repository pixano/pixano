import { z } from "zod";
import { BaseData, referenceSchema, type BaseDataFields } from "../datasetTypes";
import { Image, type ImageType } from "./Image";
import { SequenceFrame, type SequenceFrameType } from "./SequenceFrame";

export const viewSchema = z
  .object({
    item_ref: referenceSchema,
    parent_ref: referenceSchema,
  })
  .passthrough();

export type ViewType = z.infer<typeof viewSchema>; //export if needed

export type MView = Record<string, Image | SequenceFrame[]>;
export class View extends BaseData<ViewType> {
  constructor(obj: BaseDataFields<ViewType>) {
    viewSchema.parse(obj.data);
    super(obj);
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["item_ref", "parent_ref"]);
  }

  static createInstance(obj: BaseDataFields<ViewType>) {
    if (obj.table_info.base_schema === "Image")
      return new Image(obj as unknown as BaseDataFields<ImageType>);
    if (obj.table_info.base_schema === "SequenceFrame")
      return new SequenceFrame(obj as unknown as BaseDataFields<SequenceFrameType>);
    return new View(obj);
  }

  static deepCreateInstanceArrayOrPlain(
    objs: Record<string, BaseDataFields<ImageType> | BaseDataFields<SequenceFrameType>[]>,
  ): MView {
    const newObj: MView = {};
    for (const [k, vs] of Object.entries(objs)) {
      if (Array.isArray(vs)) {
        const temp: SequenceFrame[] = [];
        for (const v of vs) {
          temp.push(View.createInstance(v as unknown as BaseDataFields<ViewType>) as SequenceFrame);
        }
        newObj[k] = temp;
      } else {
        newObj[k] = View.createInstance(vs as unknown as BaseDataFields<ViewType>) as Image;
      }
    }
    return newObj;
  }
}
