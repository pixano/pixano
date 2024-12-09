/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import { BaseData, type BaseDataFields } from "../datasetTypes";

export const itemSchema = z.object({}).passthrough();
type ItemType = z.infer<typeof itemSchema>;

export class Item extends BaseData<ItemType> {
  constructor(obj: BaseDataFields<ItemType>) {
    if (obj.table_info.base_schema !== "Item") throw new Error("Not an Item");
    super(obj);
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields();
  }
}
