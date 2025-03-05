/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  BaseSchema,
  Conversation,
  Entity,
  MultiModalEntity,
  Track,
  type BaseDataFields,
  type ConversationType,
  type EntityType,
  type MultiModalEntityType,
  type TrackType,
} from "../../types";

export const createTypedEntity = (entity: BaseDataFields<EntityType>) => {
  if (entity.table_info.base_schema === BaseSchema.Track) {
    return new Track(entity as unknown as BaseDataFields<TrackType>);
  }
  if (entity.table_info.base_schema === BaseSchema.Conversation) {
    return new Conversation(entity as unknown as BaseDataFields<ConversationType>);
  }
  if (entity.table_info.base_schema === BaseSchema.MultiModalEntity) {
    return new MultiModalEntity(entity as unknown as BaseDataFields<MultiModalEntityType>);
  }
  return new Entity(entity);
};
