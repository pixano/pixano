/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import { Annotation, BaseSchema, Entity, Tracklet, type SaveItem } from "@pixano/core";

import { annotations, entities, saveData } from "../../stores/datasetItemWorkspaceStores";
import { addOrUpdateSaveItem } from "./addOrUpdateSaveItem";

function listsAreEqual(list1: string[], list2: string[]): boolean {
  if (list1.length !== list2.length) {
    return false;
  }
  const sortedList1 = list1.slice().sort();
  const sortedList2 = list2.slice().sort();
  for (let i = 0; i < sortedList1.length; i++) {
    if (sortedList1[i] !== sortedList2[i]) {
      return false;
    }
  }
  return true;
}

const deleteEntity = (entity: Entity) => {
  const save_item: SaveItem = {
    change_type: "delete",
    object: entity,
  };
  saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
  //delete eventual sub entities
  const subentities = get(entities).filter((ent) => ent.data.parent_ref.id === entity.id);
  for (const subent of subentities) {
    const save_item: SaveItem = {
      change_type: "delete",
      object: subent,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
  }
  for (const ann of entity.ui.childs || []) {
    const save_item: SaveItem = {
      change_type: "delete",
      object: ann,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
  }
  const subent_ids = subentities.map((subent) => subent.id);
  annotations.update((oldObjects) =>
    oldObjects.filter((ann) => ![entity.id, ...subent_ids].includes(ann.data.entity_ref.id)),
  );
  entities.update((oldObjects) =>
    oldObjects.filter((ent) => ent.id !== entity.id && ent.data.parent_ref.id !== entity.id),
  );
};

export const deleteObject = (entity, child: Annotation | null = null) => {
  //if no child, child is the only child, or child is last tracklet, delete full entity
  if (
    !child ||
    !entity.ui.childs ||
    entity.ui.childs.length <= 1 ||
    (child.is_type(BaseSchema.Tracklet) &&
      listsAreEqual(
        entity.ui.childs.map((ann) => ann.id),
        [...(child as Tracklet).ui.childs.map((ann) => ann.id), child.id],
      ))
  ) {
    deleteEntity(entity);
  } else {
    //if child is not the only child, delete child (with tracklet childs if child is a tracklet)
    const save_item: SaveItem = {
      change_type: "delete",
      object: child,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
    const to_delete_id = [child.id];
    if (child.is_type(BaseSchema.Tracklet)) {
      (child as Tracklet).ui.childs.forEach((ann) => {
        to_delete_id.push(ann.id);
        const save_tracklet_item: SaveItem = {
          change_type: "delete",
          object: ann,
        };
        saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_tracklet_item));
      });
    }
    annotations.update((oldObjects) => oldObjects.filter((ann) => !to_delete_id.includes(ann.id)));
    entities.update((oldObjects) =>
      oldObjects.map((ent) => {
        if (ent.id === entity.id) {
          ent.ui.childs = entity.ui.childs?.filter((ann) => !to_delete_id.includes(ann.id));
        }
        return ent;
      }),
    );
  }
};
