/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  BaseSchema,
  Conversation,
  Entity,
  Track,
  type BaseDataFields,
  type ConversationType,
  type EntityType,
  type TrackType,
} from "../../types";

export const createTypedEntity = (entity: BaseDataFields<EntityType>) => {
  if (entity.table_info.base_schema === BaseSchema.Track) {
    return new Track(entity as unknown as BaseDataFields<TrackType>);
  }
  if (entity.table_info.base_schema === BaseSchema.Conversation) {
    return new Conversation(entity as unknown as BaseDataFields<ConversationType>);
  }
  return new Entity(entity);
};
