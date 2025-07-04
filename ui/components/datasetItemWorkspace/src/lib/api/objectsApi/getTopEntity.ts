/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import { Annotation, BaseSchema, Entity } from "@pixano/core";

import { entities } from "../../stores/datasetItemWorkspaceStores";

export const getTopEntity = (obj: Annotation | Entity): Entity => {
  let entity: Entity | undefined;
  // in case this is an entity (or sub entity)
  if (
    obj.table_info.base_schema === BaseSchema.Entity ||
    obj.table_info.base_schema === BaseSchema.Track
  ) {
    //same logic, but do not use / store ui.top_entities (not present in Entity)
    entity = obj as Entity;
    const local_entities = get(entities);
    while (entity && entity.data.parent_ref.id !== "") {
      entity = local_entities.find(
        (parent_entity) => entity && parent_entity.id === entity.data.parent_ref.id,
      );
    }
    if (!entity) {
      //this should never happen
      console.error("ERROR: Unable to find top level Entity of entity", obj);
      throw new Error(`ERROR: Unable to find top level Entity of entity (id=${obj.id})`);
    }
  } else {
    const ann = obj as Annotation;
    if (ann.ui.top_entities && ann.ui.top_entities.length > 0) {
      return ann.ui.top_entities[0];
    }
    //if there is no top_entities, we build a list of the parents entities
    //first will be the top level entity, followed by sub entities in descending order
    //(last one is the direct annotation parent entity)
    ann.ui.top_entities = [];
    const local_entities = get(entities);
    entity = local_entities.find((entity) => entity.id === ann.data.entity_ref.id);
    while (entity && entity.data.parent_ref.id !== "") {
      //store entity
      ann.ui.top_entities.unshift(entity);
      entity = local_entities.find(
        (parent_entity) => entity && parent_entity.id === entity.data.parent_ref.id,
      );
    }
    if (!entity) {
      //this should never happen
      console.error("ERROR: Unable to find top level Entity of annotation", ann);
      throw new Error(`ERROR: Unable to find top level Entity of annotation (id=${ann.id})`);
    }
    //store top entity
    ann.ui.top_entities.unshift(entity);
  }
  return entity;
};
