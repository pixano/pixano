/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import { createTypedView } from "../../../utils/views";
import { BaseData, referenceSchema, type BaseDataFields } from "../datasetTypes";
import type { ImageType, SequenceFrameType } from "./Image";

export const viewSchema = z
  .object({
    item_ref: referenceSchema,
    parent_ref: referenceSchema,
  })
  .passthrough();

export type ViewType = z.infer<typeof viewSchema>; //export if needed

export abstract class View extends BaseData<ViewType> {
  constructor(obj: BaseDataFields<ViewType>) {
    viewSchema.parse(obj.data);
    super(obj);
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["item_ref", "parent_ref"]);
  }

  static deepCreateInstanceArrayOrPlain(
    objs: Record<string, BaseDataFields<ImageType> | BaseDataFields<SequenceFrameType>[]>,
  ): Record<string, View | View[]> {
    const newObj: Record<string, View | View[]> = {};
    for (const [k, vs] of Object.entries(objs)) {
      const view = createTypedView(vs as unknown as BaseDataFields<ViewType>);
      newObj[k] = view;
    }
    return newObj;
  }
}
