/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  type BaseDataFields,
  BaseSchema,
  Entity,
  type EntityType,
  Track,
  type TrackType,
} from "../../types";

export const createTypedEntity = (entity: BaseDataFields<EntityType>) => {
  if (entity.table_info.base_schema === BaseSchema.Track) {
    return new Track(entity as unknown as BaseDataFields<TrackType>);
  }
  return new Entity(entity);
};
