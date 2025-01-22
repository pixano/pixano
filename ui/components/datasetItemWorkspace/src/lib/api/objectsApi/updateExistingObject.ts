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
  type SaveItem,
  SaveShapeType,
  type Shape,
  Tracklet,
  WorkspaceType,
} from "@pixano/core";
import { sourcesStore } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { saveData } from "../../stores/datasetItemWorkspaceStores";
import { addOrUpdateSaveItem } from "./addOrUpdateSaveItem";
import { getPixanoSource } from "./getPixanoSource";

export const updateExistingObject = (objects: Annotation[], newShape: Shape): Annotation[] => {
  if (
    newShape.status === "editing" &&
    !objects.find((ann) => ann.id === newShape.shapeId) &&
    newShape.highlighted === "self"
  )
    return objects;
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
        ann.ui.highlighted = "self";
        ann.ui.displayControl = { ...ann.ui.displayControl, editing: true };
      } else {
        if (ann.is_type(BaseSchema.Tracklet)) {
          //NOTE TODO: it works, but the states with 1 tracklet highlighted in a track with several tracklet leads to bug with icon click
          const tracklet_childs_ids = (ann as Tracklet).ui.childs.map((c_ann) => c_ann.id);
          if (tracklet_childs_ids.includes(newShape.shapeId)) {
            ann.ui.highlighted = "self";
          } else {
            ann.ui.highlighted = "none";
          }
        } else {
          //NOTE: maybe we want to keep all ann of tracklet/track highlighted ? (only one in edition, but all highlighted ?)
          ann.ui.highlighted = "none";
          ann.ui.displayControl = { ...ann.ui.displayControl, editing: false };
        }
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
