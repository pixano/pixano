/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { nanoid } from "nanoid";

import {
  Entity,
  type DatasetSchema,
  type DS_NamedSchema,
  type ItemFeature,
  type SaveShape,
} from "@pixano/core";

export const defineCreatedEntity = (
  shape: SaveShape,
  features: Record<string, ItemFeature>,
  dataset_schema: DatasetSchema,
  entitySchema: DS_NamedSchema,
  parentOfSub: { id: string; name: string } | undefined = undefined,
  alternateViewRef: { id: string; name: string } | undefined = undefined,
): Entity => {
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
  return new Entity(entity);
};
