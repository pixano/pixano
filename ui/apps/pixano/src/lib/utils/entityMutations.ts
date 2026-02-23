/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ToolType } from "$lib/tools";
import { verticesToCoordsAndStates } from "$lib/utils/keypointsUtils";
import {
  Annotation,
  BaseSchema,
  BBox,
  Entity,
  Keypoints,
  Mask,
  Track,
  isVideoEntity,
  WorkspaceType,
} from "$lib/types/dataset";
import { ShapeType, type SaveShape, type Shape } from "$lib/types/shapeTypes";
import { datasetSchema, sourcesStore } from "$lib/stores/appStores.svelte";

import {
  annotations,
  entities,
  merges,
  newShape,
  selectedTool,
} from "$lib/stores/workspaceStores.svelte";
import { saveTo } from "$lib/utils/saveItemUtils";
import { isPolygonSvgMetadata, isPolygonPointsMetadata } from "$lib/utils/maskUtils";
import { sortByFrameIndex } from "$lib/utils/videoUtils";
import {
  getValidationSchemaAndFormInputs,
  getEntityProperties,
  mapShapeInputsToFeatures,
} from "$lib/utils/featureMapping";
import {
  findOrCreateSubAndTopEntities,
} from "$lib/utils/entityOperations";
import { getPixanoSource, getTopEntity } from "$lib/utils/entityLookupUtils";
import { clearHighlighting, highlightEntity } from "$lib/utils/highlightOperations";
import type { EntityProperties } from "$lib/types/workspace";

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

const deleteEntityFull = (entity: Entity) => {
  saveTo("delete", entity);
  //delete eventual sub entities
  const subentities = entities.value.filter((ent) => ent.data.parent_ref.id === entity.id);
  for (const subent of subentities) {
    saveTo("delete", subent);
  }
  for (const ann of entity.ui.childs || []) {
    saveTo("delete", ann);
  }
  const subent_ids = subentities.map((subent) => subent.id);
  annotations.update((oldObjects) =>
    oldObjects.filter((ann) => ![entity.id, ...subent_ids].includes(ann.data.entity_ref.id)),
  );
  entities.update((oldObjects) =>
    oldObjects.filter((ent) => ent.id !== entity.id && ent.data.parent_ref.id !== entity.id),
  );

  //in case we are in fusion mode, remove from to_fuse / forbids
  if (selectedTool.value.type === ToolType.Fusion) {
    merges.update((merge) => {
      merge.forbids = merge.forbids.filter((ent) => ent.id !== entity.id);
      merge.to_fuse = merge.to_fuse.filter((ent) => ent.id !== entity.id);
      return merge;
    });
  }
};

/**
 * Applies a shape edit to annotations and resets the newShape state.
 * Shared across Image, EntityLinking, and VQA workspace variants.
 */
export const applyNewShapeEditing = (shape: Shape): void => {
  annotations.update((objects) => updateExistingAnnotation(objects, shape));
  newShape.value = { status: "none" };
};

export const deleteEntity = (entity: Entity, child: Annotation | null = null) => {
  //if no child, child is the only child, or child is last tracklet, delete full entity
  if (
    !child ||
    !entity.ui.childs ||
    entity.ui.childs.length <= 1 ||
    (child.is_type(BaseSchema.Tracklet) &&
      listsAreEqual(
        entity.ui.childs.map((ann) => ann.id),
        [...(child as Track).ui.childs.map((ann) => ann.id), child.id],
      ))
  ) {
    deleteEntityFull(entity);
  } else {
    //if child is not the only child, delete child (with tracklet childs if child is a tracklet)
    saveTo("delete", child);
    const to_delete_id = [child.id];
    if (child.is_type(BaseSchema.Tracklet)) {
      (child as Track).ui.childs.forEach((ann) => {
        to_delete_id.push(ann.id);
        saveTo("delete", ann);
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

export const onDeleteTrackItemClick = (
  tracklet_as_ann: Annotation,
  itemFrameIndex: number | undefined,
  child: Annotation | null = null,
) => {
  if (!tracklet_as_ann.is_type(BaseSchema.Tracklet)) return;
  if (itemFrameIndex === undefined) return;
  const track = tracklet_as_ann as Track;
  if (track.ui.childs.length <= 1) {
    //last track child: in this case we delete track
    if (track.ui.top_entities && track.ui.top_entities[0])
      deleteEntity(track.ui.top_entities[0], track);
    return;
  }
  const anns_to_del = child
    ? [child]
    : track.ui.childs.filter((ann) => ann.ui.frame_index === itemFrameIndex);
  if (!anns_to_del) return;
  const anns_to_del_ids = anns_to_del.map((ann) => ann.id);
  let changedTrack = false;
  annotations.update((anns) =>
    anns
      .map((ann) => {
        if (ann.id === track.id && ann.is_type(BaseSchema.Tracklet)) {
          (ann as Track).ui.childs = (ann as Track).ui.childs.filter(
            (fann) => !anns_to_del_ids.includes(fann.id),
          );
          //if ann_to_del first/last of track, need to "resize" (childs should be sorted)
          if (itemFrameIndex === track.data.start_timestep) {
            (ann as Track).data.start_timestep = (ann as Track).ui.childs[0].ui.frame_index!;
            changedTrack = true;
          }
          if (itemFrameIndex === track.data.end_timestep) {
            (ann as Track).data.end_timestep = (ann as Track).ui.childs[
              (ann as Track).ui.childs.length - 1
            ].ui.frame_index!;
            changedTrack = true;
          }
        }
        return ann;
      })
      .filter((ann) => !anns_to_del_ids.includes(ann.id)),
  );
  entities.update((ents) =>
    ents.map((ent) => {
      if (isVideoEntity(ent) && ent.id === track.data.entity_ref.id) {
        ent.ui.childs = ent.ui.childs?.filter((ann) => !anns_to_del_ids.includes(ann.id));
      }
      return ent;
    }),
  );

  for (const ann_to_del of anns_to_del) {
    saveTo("delete", ann_to_del);
  }

  if (changedTrack) {
    const pixSource = getPixanoSource(sourcesStore);
    track.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
    saveTo("update", track);
  }
};

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
  let deleteEntityFlag = false;
  let deleteTrack = false;

  //get overlap target tracks
  const overlapTargetIds: string[] = overlapTargetIds_string.split(OVERLAPIDS_SEPARATOR);
  // overlapping tracks after first one will be fused, so mark them to delete
  const to_fuse_tracks = annotations.value.filter((ann) =>
    overlapTargetIds.slice(1).includes(ann.id),
  );
  const to_fuse_tracks_ids = to_fuse_tracks.map((trk) => trk.id);

  let objectProperties: EntityProperties = {};

  const { inputs: formInputs } = getValidationSchemaAndFormInputs(
    datasetSchema.value,
    child.table_info.base_schema,
  );

  const isEntityNew = selectedEntityId === "new"; //need to store it because it is reset after updating entities
  objectProperties = getEntityProperties(formInputs, {}, objectProperties);
  const features = mapShapeInputsToFeatures(objectProperties, formInputs);

  const shapeInfo: SaveShape = {
    status: "saving",
    viewRef: child.data.view_ref,
    itemId: child.data.item_ref.id,
    imageHeight: 0,
    imageWidth: 0,
  } as SaveShape;

  if (child.is_type(BaseSchema.Tracklet)) {
    const track_childs = (child as Track).ui.childs;
    to_remove_anns_ids = [child, ...track_childs].map((ann) => ann.id);
    to_move_anns = mustMerge ? [...track_childs] : [child, ...track_childs];
    //for each child, we will relink either the child itself or its top SUB entity, if exist
    const childs_tolink_map = track_childs.reduce(
      (acc, ann) => {
        acc[ann.id] = ann.ui.top_entities?.[1] ?? ann;
        return acc;
      },
      {} as Record<string, Entity | Annotation>,
    );
    const relink_set = new Set<Annotation | Entity>();
    track_childs.forEach((ann) => {
      relink_set.add(childs_tolink_map[ann.id]);
    });
    to_relink = mustMerge ? [...relink_set] : [child, ...relink_set];
    deleteTrack = mustMerge;
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
          deleteEntityFlag = true;
        }
      }
      // add to new/reaffected entity, and remove fused if any
      if (ent.id === topEntity.id) {
        ent.ui.childs = ent.ui.childs?.filter((ann) => !to_fuse_tracks_ids.includes(ann.id));
        ent.ui.childs?.push(...to_move_anns);
        //ent.ui.childs?.sort (??)
      }
      //relink sub ents (change sub entity parent_ref)
      if (to_relink.includes(ent)) {
        ent.data.parent_ref = { id: topEntity.id, name: topEntity.table_info.name };
      }
      return ent;
    });

    if (deleteEntityFlag) {
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
      if (deleteTrack && ann.is_type(BaseSchema.Tracklet)) {
        if (overlapTargetIds[0] === ann.id) {
          //add childs to new target track (the first one, others are "fused" (deleted))
          //also add childs from fused tracks
          (ann as Track).ui.childs = [
            ...(ann as Track).ui.childs,
            ...to_move_anns,
            ...to_fuse_tracks.flatMap((fann) => (fann as Track).ui.childs),
          ].sort(sortByFrameIndex);

          //target track range may change : union of current & targets
          (ann as Track).data.start_timestep = Math.min(
            (ann as Track).data.start_timestep,
            (child as Track).data.start_timestep,
            ...to_fuse_tracks.map((fann) => (fann as Track).data.start_timestep),
          );
          (ann as Track).data.end_timestep = Math.max(
            (ann as Track).data.end_timestep,
            (child as Track).data.end_timestep,
            ...to_fuse_tracks.map((fann) => (fann as Track).data.end_timestep),
          );
          //timestamps... TODO!
          (ann as Track).data.start_timestamp = (ann as Track).data.start_timestep;
          (ann as Track).data.end_timestamp = (ann as Track).data.end_timestep;
        }
      }
      return ann;
    });
    //remove fused, and origin (=child) if deleteTrack
    new_anns = new_anns.filter(
      (ann) =>
        !to_fuse_tracks_ids.includes(ann.id) && (deleteTrack ? ann.id !== child.id : true),
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
    saveTo("update", obj);
  });
  if (isEntityNew) {
    saveTo("add", topEntity);
  }
  to_fuse_tracks.forEach((trk) => {
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

export const updateExistingAnnotation = (objects: Annotation[], newShape: Shape): Annotation[] => {
  if (
    newShape.status === "editing" &&
    !objects.find((ann) => ann.id === newShape.shapeId) &&
    newShape.highlighted === "self"
  ) {
    //it is an interpolated object. Highlight anyway
    if (newShape.top_entity_id) highlightEntity(newShape.top_entity_id, false);
    return objects;
  }
  return objects.map((ann) => {
    if (newShape?.status !== "editing") return ann;
    if (newShape.highlighted === "all") {
      ann.ui.displayControl = {
        ...ann.ui.displayControl,
        highlighted: "all",
        editing: false,
      };
    }
    if (newShape.highlighted === "self") {
      if (newShape.shapeId === ann.id) {
        highlightEntity(getTopEntity(ann).id, false);
      }
    }

    if (newShape.shapeId !== ann.id) return ann;

    // Check if the object is an image Annotation (not a video -- shouldn't video don't go here)
    if (ann.ui.datasetItemType !== WorkspaceType.VIDEO) {
      let changed = false;
      if (
        (newShape.type === ShapeType.mask || newShape.type === ShapeType.polygon) &&
        ann.is_type(BaseSchema.Mask)
      ) {
        if ("counts" in newShape && Array.isArray(newShape.counts)) {
          (ann as Mask).data.counts = newShape.counts;
        }
        if (newShape.type === ShapeType.polygon) {
          const candidateMetadata = {
            geometry_mode: "polygon",
            polygon_svg: newShape.masksImageSVG,
            polygon_points: newShape.polygonPoints,
          } as Record<string, unknown>;
          ann.data.inference_metadata = {
            ...ann.data.inference_metadata,
            geometry_mode: "polygon",
            polygon_svg: isPolygonSvgMetadata(candidateMetadata) ? candidateMetadata.polygon_svg : [],
            polygon_points: isPolygonPointsMetadata(candidateMetadata) ? candidateMetadata.polygon_points : [],
          };
        }
        changed = true;
      }
      if (newShape.type === ShapeType.bbox && ann.is_type(BaseSchema.BBox)) {
        (ann as BBox).data.coords = newShape.coords;
        changed = true;
      }
      if (newShape.type === ShapeType.keypoints && ann.is_type(BaseSchema.Keypoints)) {
        const { coords, states } = verticesToCoordsAndStates(newShape.vertices);
        (ann as Keypoints).data.coords = coords;
        (ann as Keypoints).data.states = states;
        changed = true;
      }
      if (changed) {
        const pixSource = getPixanoSource(sourcesStore);
        ann.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
        saveTo("update", ann);
      }
    }
    return ann;
  });
};
