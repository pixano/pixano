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
  SequenceFrame,
  Tracklet,
  WorkspaceType,
  type SaveItem,
  type SaveShape,
} from "@pixano/core";

import { addOrUpdateSaveItem, findOrCreateSubAndTopEntities, getTopEntity } from ".";
import { datasetSchema } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { NEWTRACKLET_LENGTH } from "../../constants";
import {
  annotations,
  entities,
  mediaViews,
  saveData,
} from "../../stores/datasetItemWorkspaceStores";
import { currentFrameIndex } from "../../stores/videoViewerStores";
import type { ObjectProperties } from "../../types/datasetItemWorkspaceTypes";
import {
  getObjectProperties,
  getValidationSchemaAndFormInputs,
  mapShapeInputsToFeatures,
} from "../featuresApi";

export const relink = (child: Annotation, entity: Entity, selectedEntityId: string) => {
  //let formInputs: CreateObjectInputs = [];
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

  let endView: SequenceFrame | undefined = undefined;

  if (child.ui.datasetItemType === WorkspaceType.VIDEO) {
    let endFrameIndex = get(currentFrameIndex) + NEWTRACKLET_LENGTH + 1; //+1 for the first while loop
    const seqs = get(mediaViews)[child.data.view_ref.name];
    if (Array.isArray(seqs)) {
      while (!endView) {
        endFrameIndex = endFrameIndex - 1;
        endView = seqs.find(
          (view) =>
            view.data.frame_index === endFrameIndex &&
            view.table_info.name === child.data.view_ref.name,
        );
      }
    }
  }

  const { topEntity, subEntity, secondSubEntity } = findOrCreateSubAndTopEntities(
    selectedEntityId,
    shapeInfo,
    endView,
    features,
  );
  const linkEntity = secondSubEntity ?? subEntity ?? topEntity;

  //TODO: subEntity may not be correctly managed further down...
  // -- not really sure about how they are really handled (created or found)
  if (linkEntity.id !== topEntity.id) {
    console.warn(
      "WARNING: sub-entities may not be correctly managed for re-link. Use with caution...",
    );
  }

  let to_move_anns = [child];
  if (child.is_type(BaseSchema.Tracklet)) {
    to_move_anns = [...to_move_anns, ...(child as Tracklet).ui.childs];
  }
  const to_move_anns_ids = to_move_anns.map((ann) => ann.id);

  let deleteEntity = false;
  let saveSubEntity = false;
  let saveSecondSubEntity = false;
  const updated_entities = (ents: Entity[]) => {
    if (isEntityNew) {
      ents.push(topEntity);
      if (subEntity && !ents.includes(subEntity)) {
        ents.push(subEntity);
        saveSubEntity = true;
      }
      if (secondSubEntity && !ents.includes(secondSubEntity)) {
        ents.push(secondSubEntity);
        saveSecondSubEntity = true;
      }
    }
    let new_ents = ents.map((ent) => {
      // remove child from previous entity childs
      if (ent.id === entity.id) {
        ent.ui.childs = ent.ui.childs?.filter((ann) => !to_move_anns_ids.includes(ann.id));
        if (!ent.ui.childs || ent.ui.childs.length === 0) {
          deleteEntity = true;
        }
      }
      // add to new/reaffected entity
      if (ent.id === linkEntity.id) {
        ent.ui.childs?.push(...to_move_anns);
      }
      return ent;
    });

    if (deleteEntity) {
      new_ents = new_ents.filter((ent) => ent.id !== entity.id);
    }
    return new_ents;
  };

  // change child entity_ref
  const updated_annotations = (anns: Annotation[]) => {
    return anns.map((ann) => {
      if (to_move_anns_ids.includes(ann.id)) {
        ann.data.entity_ref = { id: linkEntity.id, name: linkEntity.table_info.name };
        ann.ui.top_entities = []; //reset top_entities
      }
      return ann;
    });
  };

  const do_update = () => {
    const upd_ents = updated_entities(get(entities));
    const upd_anns = updated_annotations(get(annotations));
    entities.set(upd_ents);
    annotations.set(upd_anns);
  };
  do_update();

  // SAVE
  to_move_anns.forEach((ann) => {
    //check, but also set moved child(s) new top_entities
    if (getTopEntity(ann) !== topEntity) {
      console.error("ERROR with Relink, something gone wrong", ann, getTopEntity(ann), topEntity);
    }
    const save_item_chid: SaveItem = {
      change_type: "update",
      object: ann,
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
  if (subEntity && saveSubEntity) {
    const save_subEntity: SaveItem = {
      change_type: "add",
      object: subEntity,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_subEntity));
  }
  if (secondSubEntity && saveSecondSubEntity) {
    const save_secondSubEntity: SaveItem = {
      change_type: "add",
      object: secondSubEntity,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_secondSubEntity));
  }

  if (deleteEntity) {
    const save_item_entity_delete: SaveItem = {
      change_type: "delete",
      object: entity,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_entity_delete));
  }
};
