/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import {
  Annotation,
  BaseSchema,
  Entity,
  Tracklet,
  type SaveItem,
  type SaveShape,
} from "@pixano/core";

import {
  addOrUpdateSaveItem,
  clearHighlighting,
  findOrCreateSubAndTopEntities,
  getTopEntity,
} from ".";
import { datasetSchema } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { annotations, entities, saveData } from "../../stores/datasetItemWorkspaceStores";
import type { ObjectProperties } from "../../types/datasetItemWorkspaceTypes";
import {
  getObjectProperties,
  getValidationSchemaAndFormInputs,
  mapShapeInputsToFeatures,
} from "../featuresApi";
import { sortByFrameIndex } from "../videoApi";

// we need to pass a list of string as a 'dataset' attribute (dataset-overlap) of option choice of HTMLSelectElement
// list is concatenated, so we try to choose a hopefully unlikely reproductible separator...
// (default, ',' is too common, and we can't use too weirds chars in HTML attribute)
export const OVERLAPIDS_SEPARATOR = "(!#!)";

export const relink = (
  child: Annotation,
  entity: Entity,
  selectedEntityId: string,
  mustMerge: boolean,
  overlapTargetIds_string: string,
) => {
  let to_relink: (Annotation | Entity)[] = [];
  let to_move_anns: Annotation[] = [];
  let to_remove_anns_ids: string[] = [];
  let deleteEntity = false;
  let deleteTracklet = false;

  //get overlap target tracklets
  const overlapTargetIds: string[] = overlapTargetIds_string.split(OVERLAPIDS_SEPARATOR);
  // overlapping tracklets after first one will be fused, so mark them to delete
  const to_fuse_tracklets = get(annotations).filter((ann) =>
    overlapTargetIds.slice(1).includes(ann.id),
  );
  const to_fuse_tracklets_ids = to_fuse_tracklets.map((trklt) => trklt.id);

  let objectProperties: ObjectProperties = {};

  const { inputs: formInputs } = getValidationSchemaAndFormInputs(
    get(datasetSchema),
    child.table_info.base_schema,
  );

  const isEntityNew = selectedEntityId === "new"; //need to store it because it is reset after updating entities
  objectProperties = getObjectProperties(formInputs, {}, objectProperties);
  const features = mapShapeInputsToFeatures(objectProperties, formInputs);

  const shapeInfo: SaveShape = {
    status: "saving",
    viewRef: child.data.view_ref,
    itemId: child.data.item_ref.id,
    imageHeight: 0,
    imageWidth: 0,
  } as SaveShape;

  if (child.is_type(BaseSchema.Tracklet)) {
    const tracklet_childs = (child as Tracklet).ui.childs;
    to_remove_anns_ids = [child, ...tracklet_childs].map((ann) => ann.id);
    to_move_anns = mustMerge ? [...tracklet_childs] : [child, ...tracklet_childs];
    //for each child, we will relink either the child itself or its top SUB entity, if exist
    const childs_tolink_map = tracklet_childs.reduce(
      (acc, ann) => {
        acc[ann.id] = ann.ui.top_entities?.[1] ?? ann;
        return acc;
      },
      {} as Record<string, Entity | Annotation>,
    );
    const relink_set = new Set<Annotation | Entity>();
    tracklet_childs.forEach((ann) => {
      relink_set.add(childs_tolink_map[ann.id]);
    });
    to_relink = mustMerge ? [...relink_set] : [child, ...relink_set];
    deleteTracklet = mustMerge;
  } else {
    to_relink = [child.ui.top_entities?.[1] ?? child];
    to_move_anns = [child];
    to_remove_anns_ids = [child.id];
  }

  const { topEntity } = findOrCreateSubAndTopEntities(selectedEntityId, shapeInfo, features);

  entities.update((ents) => {
    if (isEntityNew) {
      ents.push(topEntity);
    }
    let new_ents = ents.map((ent) => {
      // remove child from previous entity childs
      if (ent.id === entity.id) {
        ent.ui.childs = ent.ui.childs?.filter((ann) => !to_remove_anns_ids.includes(ann.id));
        if (!ent.ui.childs || ent.ui.childs.length === 0) {
          deleteEntity = true;
        }
      }
      // add to new/reaffected entity, and remove fused if any
      if (ent.id === topEntity.id) {
        ent.ui.childs = ent.ui.childs?.filter((ann) => !to_fuse_tracklets_ids.includes(ann.id));
        ent.ui.childs?.push(...to_move_anns);
        //ent.ui.childs?.sort (??)
      }
      //relink sub ents (change sub entity parent_ref)
      if (to_relink.includes(ent)) {
        ent.data.parent_ref = { id: topEntity.id, name: topEntity.table_info.name };
      }
      return ent;
    });

    if (deleteEntity) {
      new_ents = new_ents.filter((ent) => ent.id !== entity.id);
    }
    return new_ents;
  });

  // change child entity_ref
  annotations.update((anns: Annotation[]) => {
    let new_anns = anns.map((ann) => {
      if (to_relink.includes(ann)) {
        ann.data.entity_ref = { id: topEntity.id, name: topEntity.table_info.name };
        ann.ui.top_entities = []; //reset top_entities
      }
      if (deleteTracklet && ann.is_type(BaseSchema.Tracklet)) {
        if (overlapTargetIds[0] === ann.id) {
          //add childs to new target tracklet (the first one, others are "fused" (deleted))
          //also add childs from fused tracklets
          (ann as Tracklet).ui.childs = [
            ...(ann as Tracklet).ui.childs,
            ...to_move_anns,
            ...to_fuse_tracklets.flatMap((fann) => (fann as Tracklet).ui.childs),
          ].sort(sortByFrameIndex);

          //target tracklet range may change : union of current & targets
          (ann as Tracklet).data.start_timestep = Math.min(
            (ann as Tracklet).data.start_timestep,
            (child as Tracklet).data.start_timestep,
            ...to_fuse_tracklets.map((fann) => (fann as Tracklet).data.start_timestep),
          );
          (ann as Tracklet).data.end_timestep = Math.max(
            (ann as Tracklet).data.end_timestep,
            (child as Tracklet).data.end_timestep,
            ...to_fuse_tracklets.map((fann) => (fann as Tracklet).data.end_timestep),
          );
          //timestamps... TODO!
          (ann as Tracklet).data.start_timestamp = (ann as Tracklet).data.start_timestep;
          (ann as Tracklet).data.end_timestamp = (ann as Tracklet).data.end_timestep;
        }
      }
      return ann;
    });
    //remove fused, and origin (=child) if deleteTracklet
    new_anns = new_anns.filter(
      (ann) =>
        !to_fuse_tracklets_ids.includes(ann.id) && (deleteTracklet ? ann.id !== child.id : true),
    );
    return new_anns;
  });

  //reset moved child(s) new top_entities + check
  to_move_anns.forEach((ann) => {
    ann.ui.top_entities = [];
    if (getTopEntity(ann) !== topEntity) {
      console.error("ERROR with Relink, something gone wrong", ann, getTopEntity(ann), topEntity);
    }
  });

  // SAVE
  to_relink.forEach((obj) => {
    const save_item_chid: SaveItem = {
      change_type: "update",
      object: obj,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_chid));
  });
  if (isEntityNew) {
    const save_item_entity: SaveItem = {
      change_type: "add",
      object: topEntity,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_entity));
  }
  to_fuse_tracklets.forEach((trklt) => {
    const save_item_fused_tracklet_delete: SaveItem = {
      change_type: "delete",
      object: trklt,
    };
    saveData.update((current_sd) =>
      addOrUpdateSaveItem(current_sd, save_item_fused_tracklet_delete),
    );
  });
  if (deleteTracklet) {
    const save_item_tracklet_delete: SaveItem = {
      change_type: "delete",
      object: child,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_tracklet_delete));
  }
  if (deleteEntity) {
    const save_item_entity_delete: SaveItem = {
      change_type: "delete",
      object: entity,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_entity_delete));
  }
  clearHighlighting();
};
