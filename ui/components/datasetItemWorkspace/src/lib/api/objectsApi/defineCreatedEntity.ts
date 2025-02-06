/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  BaseSchema,
  Conversation,
  type DatasetSchema,
  type DS_NamedSchema,
  Entity,
  type ItemFeature,
  type SaveShape,
  Track,
} from "@pixano/core";
import { nanoid } from "nanoid";

export const defineCreatedEntity = (
  shape: SaveShape,
  features: Record<string, ItemFeature>,
  dataset_schema: DatasetSchema,
  entitySchema: DS_NamedSchema,
  parentOfSub: { id: string; name: string } | undefined = undefined,
  alternateViewRef: { id: string; name: string } | undefined = undefined,
): Entity | Track => {
  const table = entitySchema.name;
  const now = new Date(Date.now()).toISOString().replace(/Z$/, "+00:00");
  const entity = {
    id: nanoid(10),
    created_at: now,
    updated_at: now,
    table_info: { name: table, group: "entities", base_schema: entitySchema.base_schema },
    data: {
      item_ref: { name: "item", id: shape.itemId },
      view_ref: parentOfSub
        ? alternateViewRef
          ? alternateViewRef
          : shape.viewRef
        : { name: "", id: "" },
      parent_ref: parentOfSub ? parentOfSub : { name: "", id: "" },
    },
  };
  if (features) {
    for (const feat of Object.values(features)) {
      entity.data = { ...entity.data, [feat.name]: feat.value };
    }
  }
  if (entitySchema.base_schema === BaseSchema.Track) {
    //already done just before, but lint require entity.data.name, and can't know it's done...
    const track = {
      ...entity,
      data: { ...entity.data, name: "name" in features ? (features["name"].value as string) : "" },
    };
    return new Track(track);
  } else if (entitySchema.base_schema === BaseSchema.Conversation) {
    const conversation = {
      ...entity,
      data: { ...entity.data, kind: "name" }, //TODO kind ??
    };
    return new Conversation(conversation);
  } else return new Entity(entity);
};
