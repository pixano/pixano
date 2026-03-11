/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { annotations, entities } from "$lib/stores/workspaceStores.svelte";
import {
  Annotation,
  BaseSchema,
  Entity,
  Tracklet,
} from "$lib/types/dataset";
import { type SaveShape } from "$lib/types/shapeTypes";
import type { EntityProperties } from "$lib/types/workspace";
import { getTopEntity } from "$lib/utils/entityLookupUtils";
import {
  appendAnnotationsSorted,
  findOrCreateEntity,
  removeAnnotationsByIds,
} from "$lib/utils/entityOperations";
import {
  getEntityProperties,
  getValidationSchemaAndFormInputs,
  mapShapeInputsToFeatures,
} from "$lib/utils/featureMapping";
import { clearHighlighting } from "$lib/utils/highlightOperations";
import { saveTo } from "$lib/utils/saveItemUtils";
import { sortByFrameIndex } from "$lib/utils/videoUtils";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

// We need to pass a list of string as a 'dataset' attribute (dataset-overlap) of option choice of HTMLSelectElement.
// List is concatenated, so we choose an unlikely separator.
export const OVERLAPIDS_SEPARATOR = "(!#!)";

export const relink = (
  child: Annotation,
  entity: Entity,
  selectedEntityId: string,
  mustMerge: boolean,
  overlapTargetIdsString: string,
  workspaceManifest: WorkspaceManifest,
): void => {
  let toRelink: (Annotation | Entity)[] = [];
  let toMoveAnnotations: Annotation[] = [];
  let toRemoveAnnotationIds: string[] = [];
  let deleteEntityFlag = false;
  let deleteTrack = false;

  // get overlap target tracks
  const overlapTargetIds: string[] = overlapTargetIdsString.split(OVERLAPIDS_SEPARATOR);
  // overlapping tracks after first one will be fused, so mark them to delete
  const tracksToFuse = annotations.value.filter((ann) => overlapTargetIds.slice(1).includes(ann.id));
  const tracksToFuseIds = tracksToFuse.map((trk) => trk.id);
  const tracksToFuseIdSet = new Set(tracksToFuseIds);

  let objectProperties: EntityProperties = {};
  const { inputs: formInputs } = getValidationSchemaAndFormInputs(
    workspaceManifest,
    child.table_info.base_schema,
  );

  const isEntityNewSelection = selectedEntityId === "new"; // keep before entities.update, selection state can reset
  objectProperties = getEntityProperties(formInputs, {}, objectProperties);
  const features = mapShapeInputsToFeatures(objectProperties, formInputs);

  const shapeInfo: SaveShape = {
    status: "saving",
    viewRef: { name: child.data.view_name, id: child.data.frame_id },
    itemId: child.data.item_id,
    imageHeight: 0,
    imageWidth: 0,
  } as SaveShape;

  if (child.is_type(BaseSchema.Tracklet)) {
    const trackChilds = (child as Tracklet).ui.childs;
    toRemoveAnnotationIds = [child, ...trackChilds].map((ann) => ann.id);
    toMoveAnnotations = mustMerge ? [...trackChilds] : [child, ...trackChilds];

    // For each child we relink either the child itself or its top sub-entity (if any).
    const childsToLinkMap = trackChilds.reduce(
      (acc, ann) => {
        acc[ann.id] = ann;
        return acc;
      },
      {} as Record<string, Entity | Annotation>,
    );
    const relinkSet = new Set<Annotation | Entity>();
    trackChilds.forEach((ann) => {
      relinkSet.add(childsToLinkMap[ann.id]);
    });
    toRelink = mustMerge ? [...relinkSet] : [child, ...relinkSet];
    deleteTrack = mustMerge;
  } else {
    toRelink = [child];
    toMoveAnnotations = [child];
    toRemoveAnnotationIds = [child.id];
  }

  const targetEntity = findOrCreateEntity(
    selectedEntityId,
    shapeInfo,
    features,
    workspaceManifest,
  );
  const shouldAddTopEntity =
    isEntityNewSelection || !entities.value.some((existingEntity) => existingEntity.id === targetEntity.id);

  entities.update((ents) => {
    if (shouldAddTopEntity && !ents.some((existingEntity) => existingEntity.id === targetEntity.id)) {
      ents.push(targetEntity);
    }

    let nextEntities = ents.map((ent) => {
      // remove child from previous entity childs
      if (ent.id === entity.id) {
        ent.ui.childs = removeAnnotationsByIds(ent.ui.childs, toRemoveAnnotationIds);
        if (!ent.ui.childs || ent.ui.childs.length === 0) {
          deleteEntityFlag = true;
        }
      }

      // add to new/reaffected entity, and remove fused if any
      if (ent.id === targetEntity.id) {
        const withoutFused = removeAnnotationsByIds(ent.ui.childs, tracksToFuseIdSet);
        ent.ui.childs = appendAnnotationsSorted(withoutFused, toMoveAnnotations);
      }

      if (toRelink.includes(ent)) {
        ent.data.parent_id = "";
      }
      return ent;
    });

    if (deleteEntityFlag) {
      nextEntities = nextEntities.filter((ent) => ent.id !== entity.id);
    }

    return nextEntities;
  });

  // change child entity_ref
  annotations.update((anns: Annotation[]) => {
    let nextAnnotations = anns.map((ann) => {
        if (toRelink.includes(ann)) {
        ann.data.entity_id = targetEntity.id;
        ann.ui.top_entities = []; // reset top_entities
      }
      if (deleteTrack && ann.is_type(BaseSchema.Tracklet)) {
        if (overlapTargetIds[0] === ann.id) {
          // add childs to new target track (the first one), others are fused
          // also add childs from fused tracks
          (ann as Tracklet).ui.childs = [
            ...(ann as Tracklet).ui.childs,
            ...toMoveAnnotations,
            ...tracksToFuse.flatMap((fann) => (fann as Tracklet).ui.childs),
          ].sort(sortByFrameIndex);

          // target track range may change: union of current & targets
          (ann as Tracklet).data.start_frame = Math.min(
            (ann as Tracklet).data.start_frame,
            (child as Tracklet).data.start_frame,
            ...tracksToFuse.map((fann) => (fann as Tracklet).data.start_frame),
          );
          (ann as Tracklet).data.end_frame = Math.max(
            (ann as Tracklet).data.end_frame,
            (child as Tracklet).data.end_frame,
            ...tracksToFuse.map((fann) => (fann as Tracklet).data.end_frame),
          );

          // timestamps... TODO!
          (ann as Tracklet).data.start_timestamp = (ann as Tracklet).data.start_frame;
          (ann as Tracklet).data.end_timestamp = (ann as Tracklet).data.end_frame;
        }
      }
      return ann;
    });

    // remove fused, and origin (=child) if deleteTrack
    nextAnnotations = nextAnnotations.filter(
      (ann) => !tracksToFuseIdSet.has(ann.id) && (deleteTrack ? ann.id !== child.id : true),
    );
    return nextAnnotations;
  });

  // reset moved child(s) new top_entities + check
  toMoveAnnotations.forEach((ann) => {
    ann.ui.top_entities = [];
    if (getTopEntity(ann) !== targetEntity) {
      console.error("ERROR with Relink, something gone wrong", ann, getTopEntity(ann), targetEntity);
    }
  });

  // save
  toRelink.forEach((obj) => {
    saveTo("update", obj);
  });
  if (shouldAddTopEntity) {
    saveTo("add", targetEntity);
  }
  tracksToFuse.forEach((trk) => {
    saveTo("delete", trk);
  });
  if (deleteTrack) {
    saveTo("delete", child);
  }
  if (deleteEntityFlag) {
    saveTo("delete", entity);
  }

  clearHighlighting();
};
