/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import { createTypedEntity } from "../../../utils/entities";
import type { Annotation } from "../annotations";
import { BaseSchema } from "../BaseSchema";
import { BaseData, type BaseDataFields, referenceSchema } from "../datasetTypes";

export const entitySchema = z
  .object({
    item_ref: referenceSchema,
    view_ref: referenceSchema,
    parent_ref: referenceSchema,
  })
  .passthrough();

export type EntityType = z.infer<typeof entitySchema>; //export if needed

export type EntityUIFields = {
  childs?: Annotation[];
};

export class Entity extends BaseData<EntityType> {
  //UI fields
  ui: EntityUIFields = { childs: [] };

  constructor(obj: BaseDataFields<EntityType>) {
    entitySchema.parse(obj.data);
    super(obj);
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["item_ref", "view_ref", "parent_ref"]);
  }

  static deepCreateInstanceArray(
    objs: Record<string, BaseDataFields<EntityType>[]>,
  ): Record<string, Entity[]> {
    const newObj: Record<string, Entity[]> = {};
    for (const [k, vs] of Object.entries(objs)) {
      newObj[k] = [];
      for (const v of vs) {
        newObj[k].push(createTypedEntity(v));
      }
    }
    return newObj;
  }

  is_type(type: BaseSchema): boolean {
    if (!this) {
      console.error("ERROR: do not use 'is_*' on uninitialized object");
      return false;
    }
    return this.table_info.base_schema === type;
  }

  get is_track(): boolean {
    return this.is_type(BaseSchema.Track);
  }
  get is_conversation(): boolean {
    return this.is_type(BaseSchema.Conversation);
  }
}
