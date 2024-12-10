/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Annotation, Entity } from "@pixano/core";

export const getTopEntity = (ann: Annotation, entities: Entity[]): Entity => {
  if (ann.ui.top_entities && ann.ui.top_entities.length > 0) {
    return ann.ui.top_entities[0];
  }
  //if there is no top_entities, we build a list of the parents entities
  //first will be the top level entity, followed by sub entities in descending order
  //(last one is the direct annotation parent entity)
  ann.ui.top_entities = [];
  let entity = entities.find((entity) => entity.id === ann.data.entity_ref.id);
  while (entity && entity.data.parent_ref.id !== "") {
    //store entity
    ann.ui.top_entities.unshift(entity);
    entity = entities.find(
      (parent_entity) => entity && parent_entity.id === entity.data.parent_ref.id,
    );
  }
  if (!entity) {
    //this should never happen
    console.error("ERROR: Unable to found top level Entity of annotation", ann);
    throw new Error(`ERROR: Unable to found top level Entity of annotation (id=${ann.id})`);
  }
  //store top entity
  ann.ui.top_entities.unshift(entity);
  return entity;
};
