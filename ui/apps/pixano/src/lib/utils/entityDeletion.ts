/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { sourcesStore } from "$lib/stores/appStores.svelte";
import {
  annotations,
  entities,
  merges,
  selectedTool,
} from "$lib/stores/workspaceStores.svelte";
import { ToolType } from "$lib/tools";
import { Annotation, BaseSchema, Entity, isVideoEntity, Tracklet } from "$lib/types/dataset";
import { saveUpdatedWithPixanoSource } from "$lib/utils/entityLookupUtils";
import { removeAnnotationsByIds } from "$lib/utils/entityOperations";
import { saveTo } from "$lib/utils/saveItemUtils";

function listsAreEqual(list1: string[], list2: string[]): boolean {
  if (list1.length !== list2.length) {
    return false;
  }
  const sortedList1 = list1.slice().sort();
  const sortedList2 = list2.slice().sort();
  for (let i = 0; i <sortedList1.length; i++) {
    if (sortedList1[i] !== sortedList2[i]) {
      return false;
    }
  }
  return true;
}

const deleteEntityFull = (entity: Entity): void => {
  saveTo("delete", entity);
  // delete eventual sub entities
  const subentities = entities.value.filter((ent) => ent.data.parent_id === entity.id);
  for (const subent of subentities) {
    saveTo("delete", subent);
  }
  for (const ann of entity.ui.childs || []) {
    saveTo("delete", ann);
  }

  const subEntityIds = subentities.map((subent) => subent.id);
  annotations.update((oldObjects) =>
    oldObjects.filter((ann) => ![entity.id, ...subEntityIds].includes(ann.data.entity_id)),
  );
  entities.update((oldObjects) =>
    oldObjects.filter((ent) => ent.id !== entity.id && ent.data.parent_id !== entity.id),
  );

  // in case we are in fusion mode, remove from to_fuse / forbids
  if (selectedTool.value.type === ToolType.Fusion) {
    merges.update((merge) => {
      merge.forbids = merge.forbids.filter((ent) => ent.id !== entity.id);
      merge.to_fuse = merge.to_fuse.filter((ent) => ent.id !== entity.id);
      return merge;
    });
  }
};

export const deleteEntity = (entity: Entity, child: Annotation | null = null): void => {
  // if no child, child is the only child, or child is last tracklet, delete full entity
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
    deleteEntityFull(entity);
  } else {
    // if child is not the only child, delete child (with tracklet childs if child is a tracklet)
    saveTo("delete", child);
    const toDeleteIdSet = new Set<string>([child.id]);
    if (child.is_type(BaseSchema.Tracklet)) {
      (child as Tracklet).ui.childs.forEach((ann) => {
        toDeleteIdSet.add(ann.id);
        saveTo("delete", ann);
      });
    }

    annotations.update((oldObjects) => oldObjects.filter((ann) => !toDeleteIdSet.has(ann.id)));
    entities.update((oldObjects) =>
      oldObjects.map((ent) => {
        if (ent.id === entity.id) {
          ent.ui.childs = removeAnnotationsByIds(entity.ui.childs, toDeleteIdSet);
        }
        return ent;
      }),
    );
  }
};

export const onDeleteTrackItemClick = (
  trackletAsAnnotation: Annotation,
  itemFrameIndex: number | undefined,
  child: Annotation | null = null,
): void => {
  if (!trackletAsAnnotation.is_type(BaseSchema.Tracklet)) return;
  if (itemFrameIndex === undefined) return;

  const track = trackletAsAnnotation as Tracklet;
  if (track.ui.childs.length <= 1) {
    // last track child: in this case we delete track
    if (track.ui.top_entities && track.ui.top_entities[0]) {
      deleteEntity(track.ui.top_entities[0], track);
    }
    return;
  }

  const annotationsToDelete = child
    ? [child]
    : track.ui.childs.filter((ann) => ann.ui.frame_index === itemFrameIndex);
  if (annotationsToDelete.length === 0) return;

  const annotationsToDeleteIds = new Set(annotationsToDelete.map((ann) => ann.id));
  let changedTrack = false;

  annotations.update((anns) =>
    anns
      .map((ann) => {
        if (ann.id === track.id && ann.is_type(BaseSchema.Tracklet)) {
          (ann as Tracklet).ui.childs = (ann as Tracklet).ui.childs.filter(
            (fann) => !annotationsToDeleteIds.has(fann.id),
          );

          // if ann_to_del first/last of track, need to "resize" (childs should be sorted)
          if (itemFrameIndex === track.data.start_frame) {
            (ann as Tracklet).data.start_frame = (ann as Tracklet).ui.childs[0].ui.frame_index!;
            changedTrack = true;
          }
          if (itemFrameIndex === track.data.end_frame) {
            (ann as Tracklet).data.end_frame = (ann as Tracklet).ui.childs[
              (ann as Tracklet).ui.childs.length - 1
            ].ui.frame_index!;
            changedTrack = true;
          }
        }
        return ann;
      })
      .filter((ann) => !annotationsToDeleteIds.has(ann.id)),
  );

  entities.update((ents) =>
    ents.map((ent) => {
      if (isVideoEntity(ent) && ent.id === track.data.entity_id) {
        ent.ui.childs = removeAnnotationsByIds(ent.ui.childs, annotationsToDeleteIds);
      }
      return ent;
    }),
  );

  for (const annToDelete of annotationsToDelete) {
    saveTo("delete", annToDelete);
  }

  if (changedTrack) {
    saveUpdatedWithPixanoSource(track, sourcesStore);
  }
};
