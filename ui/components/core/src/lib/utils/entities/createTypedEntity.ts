/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Entity, type BaseDataFields, type EntityType } from "../../types";

export const createTypedEntity = (entity: BaseDataFields<EntityType>) => {
  return new Entity(entity);
};
