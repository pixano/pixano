/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  Annotation,
  BaseSchema,
  BBox,
  Keypoints,
  Mask,
  SaveShapeType,
  WorkspaceType,
  type SaveItem,
  type Shape,
} from "@pixano/core";

import { getTopEntity, highlightObject } from ".";
import { sourcesStore } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { saveData } from "../../stores/datasetItemWorkspaceStores";
import { addOrUpdateSaveItem } from "./addOrUpdateSaveItem";
import { getPixanoSource } from "./getPixanoSource";

export const updateExistingObject = (objects: Annotation[], newShape: Shape): Annotation[] => {
  if (
    newShape.status === "editing" &&
    !objects.find((ann) => ann.id === newShape.shapeId) &&
    newShape.highlighted === "self"
  ) {
    //it is an interpolated object. Highlight anyway
    if (newShape.top_entity) highlightObject(newShape.top_entity, false);
    return objects;
  }
  return objects.map((ann) => {
    if (newShape?.status !== "editing") return ann;
    if (newShape.highlighted === "all") {
      ann.ui.highlighted = "all";
      ann.ui.displayControl = {
        ...ann.ui.displayControl,
        editing: false,
      };
    }
    if (newShape.highlighted === "self") {
      if (newShape.shapeId === ann.id) {
        highlightObject(getTopEntity(ann), false);
      }
    }

    if (newShape.shapeId !== ann.id) return ann;

    // Check if the object is an image Annotation
    if (ann.ui.datasetItemType === WorkspaceType.IMAGE) {
      let changed = false;
      if (newShape.type === SaveShapeType.mask && ann.is_type(BaseSchema.Mask)) {
        (ann as Mask).data.counts = newShape.counts;
        changed = true;
      }
      if (newShape.type === SaveShapeType.bbox && ann.is_type(BaseSchema.BBox)) {
        (ann as BBox).data.coords = newShape.coords;
        changed = true;
      }
      if (newShape.type === SaveShapeType.keypoints && ann.is_type(BaseSchema.Keypoints)) {
        const coords = [];
        const states = [];
        for (const vertex of newShape.vertices) {
          coords.push(vertex.x);
          coords.push(vertex.y);
          if (vertex.features.state) states.push(vertex.features.state);
        }
        (ann as Keypoints).data.coords = coords;
        (ann as Keypoints).data.states = states;
        changed = true;
      }
      if (changed) {
        const pixSource = getPixanoSource(sourcesStore);
        ann.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
        const save_item: SaveItem = {
          change_type: "update",
          object: ann,
        };
        saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
      }
    }
    return ann;
  });
};
