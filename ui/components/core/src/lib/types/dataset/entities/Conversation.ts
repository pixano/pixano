/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

import { BaseSchema } from "../BaseSchema";
import { type BaseDataFields } from "../datasetTypes";
import { Entity, type EntityType } from "./Entity";

export const conversationSchema = z
  .object({
    kind: z.string(),
  })
  .passthrough();

export type ConversationType = z.infer<typeof conversationSchema>;

export class Conversation extends Entity {
  declare data: ConversationType & EntityType;

  constructor(obj: BaseDataFields<ConversationType>) {
    if (obj.table_info.base_schema !== BaseSchema.Conversation)
      throw new Error("Not a Conversation");
    conversationSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<EntityType>);
    this.data = obj.data as ConversationType & EntityType;
  }

  static nonFeaturesFields(): string[] {
    return super.nonFeaturesFields().concat(["kind"]);
  }
}
