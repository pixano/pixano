/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

import { BaseSchema } from "../BaseSchema";
import { type BaseDataFields } from "../datasetTypes";
import { Entity, type EntityType } from "./Entity";

export const multiModalEntitySchema = z
  .object({
    name: z.string(),
  })
  .passthrough();

export type MultiModalEntityType = z.infer<typeof multiModalEntitySchema>;

export class MultiModalEntity extends Entity {
  declare data: MultiModalEntityType & EntityType;

  constructor(obj: BaseDataFields<MultiModalEntityType>) {
    if (obj.table_info.base_schema !== BaseSchema.MultiModalEntity)
      throw new Error("Not a MultiModalEntity");
    multiModalEntitySchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<EntityType>);
    this.data = obj.data as MultiModalEntityType & EntityType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["name"]);
  }
}
