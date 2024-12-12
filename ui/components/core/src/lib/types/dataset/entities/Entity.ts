/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import { createTypedEntity } from "../../../utils/entities";
import type { Annotation } from "../annotations";
import { BaseData, type BaseDataFields, referenceSchema } from "../datasetTypes";
import { BaseSchema } from "../BaseSchema";

export const entitySchema = z
  .object({
    item_ref: referenceSchema,
    view_ref: referenceSchema,
    parent_ref: referenceSchema,
  })
  .passthrough();

export type EntityType = z.infer<typeof entitySchema>; //export if needed

export class Entity extends BaseData<EntityType> {
  //UI fields
  ui: {
    childs?: Annotation[];
  } = { childs: [] };

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
    // eslint-disable-next-line @typescript-eslint/no-unsafe-enum-comparison
    return this.table_info.base_schema === type;
  }

  get is_track(): boolean {
    return this.is_type(BaseSchema.Track);
  }
  get is_conversation(): boolean {
    return this.is_type(BaseSchema.Conversation);
  }
}
