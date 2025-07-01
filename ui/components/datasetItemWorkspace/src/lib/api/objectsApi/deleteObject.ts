/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import { ToolType } from "@pixano/canvas2d/src/tools";
import { Annotation, BaseSchema, Entity, Tracklet, type SaveItem } from "@pixano/core";

import { sourcesStore } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import {
  annotations,
  entities,
  merges,
  saveData,
  selectedTool,
} from "../../stores/datasetItemWorkspaceStores";
import { addOrUpdateSaveItem } from "./addOrUpdateSaveItem";
import { getPixanoSource } from "./getPixanoSource";

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

  //in case we are in fusion mode, remove from to_fuse / forbids
  if (get(selectedTool).type === ToolType.Fusion) {
    merges.update((merge) => {
      merge.forbids = merge.forbids.filter((ent) => ent.id !== entity.id);
      merge.to_fuse = merge.to_fuse.filter((ent) => ent.id !== entity.id);
      return merge;
    });
  }
};

export const deleteObject = (entity: Entity, child: Annotation | null = null) => {
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

export const onDeleteItemClick = (
  tracklet_as_ann: Annotation,
  itemFrameIndex: number | undefined,
  child: Annotation | null = null,
) => {
  if (!tracklet_as_ann.is_type(BaseSchema.Tracklet)) return;
  if (itemFrameIndex === undefined) return;
  const tracklet = tracklet_as_ann as Tracklet;
  if (tracklet.ui.childs.length <= 1) {
    //last tracklet child: in this case we delete tracklet
    if (tracklet.ui.top_entities && tracklet.ui.top_entities[0])
      deleteObject(tracklet.ui.top_entities[0], tracklet);
    return;
  }
  const anns_to_del = child
    ? [child]
    : tracklet.ui.childs.filter((ann) => ann.ui.frame_index === itemFrameIndex);
  if (!anns_to_del) return;
  const anns_to_del_ids = anns_to_del.map((ann) => ann.id);
  let changed_tracklet = false;
  annotations.update((anns) =>
    anns
      .map((ann) => {
        if (ann.id === tracklet.id && ann.is_type(BaseSchema.Tracklet)) {
          (ann as Tracklet).ui.childs = (ann as Tracklet).ui.childs.filter(
            (fann) => !anns_to_del_ids.includes(fann.id),
          );
          //if ann_to_del first/last of tracklet, need to "resize" (childs should be sorted)
          if (itemFrameIndex === tracklet.data.start_timestep) {
            (ann as Tracklet).data.start_timestep = (ann as Tracklet).ui.childs[0].ui.frame_index!;
            changed_tracklet = true;
          }
          if (itemFrameIndex === tracklet.data.end_timestep) {
            (ann as Tracklet).data.end_timestep = (ann as Tracklet).ui.childs[
              (ann as Tracklet).ui.childs.length - 1
            ].ui.frame_index!;
            changed_tracklet = true;
          }
        }
        return ann;
      })
      .filter((ann) => !anns_to_del_ids.includes(ann.id)),
  );
  entities.update((ents) =>
    ents.map((ent) => {
      if (ent.is_track && ent.id === tracklet.data.entity_ref.id) {
        ent.ui.childs = ent.ui.childs?.filter((ann) => !anns_to_del_ids.includes(ann.id));
      }
      return ent;
    }),
  );

  for (const ann_to_del of anns_to_del) {
    const save_del_ann: SaveItem = {
      change_type: "delete",
      object: ann_to_del,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_del_ann));
  }

  if (changed_tracklet) {
    const pixSource = getPixanoSource(sourcesStore);
    tracklet.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
    const save_upd_tracklet: SaveItem = {
      change_type: "update",
      object: tracklet,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_upd_tracklet));
  }
};
