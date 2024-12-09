import { z } from "zod";
import { createTypedEntity } from "../../../utils/entities";
import type { Annotation } from "../annotations";
import { BaseData, type BaseDataFields, referenceSchema } from "../datasetTypes";

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

  get is_track(): boolean {
    if (!this) {
      console.error("ERROR: do not use 'is_track' on uninitialized object");
      return false;
    }
    return this.table_info.base_schema === "Track";
  }
}
