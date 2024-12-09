import { type BaseDataFields, Entity, type EntityType, Track, type TrackType } from "../../types";

export const createTypedEntity = (entity: BaseDataFields<EntityType>) => {
  if (entity.table_info.base_schema === "Track") {
    return new Track(entity as unknown as BaseDataFields<TrackType>);
  }
  return new Entity(entity);
};
