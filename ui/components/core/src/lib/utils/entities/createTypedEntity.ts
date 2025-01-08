/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  type BaseDataFields,
  BaseSchema,
  Conversation,
  type ConversationType,
  Entity,
  type EntityType,
  Track,
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
