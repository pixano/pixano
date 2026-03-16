/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { PRE_ANNOTATION } from "$lib/constants/workspaceConstants";
import { entities } from "$lib/stores/workspaceStores.svelte";
import {
  Annotation,
  BaseSchema,
  Entity,
  entityHasTracklets,
  WorkspaceType,
  type AnnotationThumbnail,
  type BBox,
  type Mask,
  type Schema,
  type Tracklet,
} from "$lib/types/dataset";
import type { ItemsMeta, MView } from "$lib/types/workspace";
import type { WorkspaceManifest, WorkspaceTableGroup } from "$lib/workspace/manifest";
import { resolveWorkspaceTable } from "$lib/workspace/manifest";

/**
 * Pure variant of getTopEntity that accepts an entities list directly,
 * avoiding reading the store through the Svelte 5 proxy during loadData().
 */
export const getTopEntityFromList = (obj: Annotation | Entity, entitiesList: Entity[]): Entity => {
  let entity: Entity | undefined;
  if (obj.table_info.group === "entities") {
    entity = obj as Entity;
    while (entity && entity.data.parent_id !== "") {
      entity = entitiesList.find(
        (parent_entity) => entity && parent_entity.id === entity.data.parent_id,
      );
    }
    if (!entity) {
      console.error("ERROR: Unable to find top level Entity of entity", obj);
      throw new Error(`ERROR: Unable to find top level Entity of entity (id=${obj.id})`);
    }
  } else {
    const ann = obj as Annotation;
    if (ann.ui.top_entities && ann.ui.top_entities.length > 0) {
      return ann.ui.top_entities[0];
    }
    ann.ui.top_entities = [];
    entity = entitiesList.find((entity) => entity.id === ann.data.entity_id);
    while (entity && entity.data.parent_id !== "") {
      ann.ui.top_entities.unshift(entity);
      entity = entitiesList.find(
        (parent_entity) => entity && parent_entity.id === entity.data.parent_id,
      );
    }
    if (!entity) {
      console.error("ERROR: Unable to find top level Entity of annotation", ann);
      throw new Error(`ERROR: Unable to find top level Entity of annotation (id=${ann.id})`);
    }
    ann.ui.top_entities.unshift(entity);
  }
  return entity;
};

export const getTopEntity = (obj: Annotation | Entity): Entity => {
  return getTopEntityFromList(obj, entities.value);
};

type SourceFieldStampedSchema = Schema & {
  data: {
    source_type?: string;
    source_name?: string;
    source_metadata?: string;
  };
};

export const PIXANO_SOURCE = {
  type: "other",
  name: "Pixano",
  metadata: "{}",
} as const;

export const applyPixanoSourceFields = <T extends SourceFieldStampedSchema>(obj: T): T => {
  obj.data.source_type = PIXANO_SOURCE.type;
  obj.data.source_name = PIXANO_SOURCE.name;
  obj.data.source_metadata = PIXANO_SOURCE.metadata;
  return obj;
};

export const getAnnotationsToPreAnnotate = (objects: Annotation[]): Annotation[] => {
  return objects.filter(
    (object) => object.data.source_name === PRE_ANNOTATION && !object.ui.review_state,
  );
};

export const getTable = (
  workspaceManifest: WorkspaceManifest,
  group: WorkspaceTableGroup,
  baseSchema: BaseSchema,
): string => {
  const table = resolveWorkspaceTable(workspaceManifest, group, baseSchema);
  if (table) {
    return table;
  }
  throw new Error(`No table found for group '${group}' and base schema '${baseSchema}'.`);
};

export const sortAndFilterAnnotations = (
  objects: Annotation[],
  confidenceFilterValue: number[],
  currentFrameIndex: number,
): Annotation[] => {
  return objects
    .filter((object) => {
      if (object.ui.datasetItemType === WorkspaceType.IMAGE && object.is_type(BaseSchema.BBox)) {
        const confidence = (object as BBox).data.confidence || 0;
        return confidence >= confidenceFilterValue[0];
      }
      if (
        object.ui.datasetItemType === WorkspaceType.VIDEO &&
        object.is_type(BaseSchema.BBox) &&
        object.ui.frame_index === currentFrameIndex
      ) {
        const confidence = (object as BBox).data.confidence || 0;
        return confidence >= confidenceFilterValue[0];
      }
      return false;
    })
    .sort((a, b) => {
      const firstBoxXPosition = (a as BBox).data.coords[0] || 0;
      const secondBoxXPosition = (b as BBox).data.coords[0] || 0;
      return firstBoxXPosition - secondBoxXPosition;
    });
};

export const defineAnnotationThumbnail = (
  metas: ItemsMeta | undefined,
  views: MView,
  object: Annotation,
): AnnotationThumbnail | null => {
  let coords: number[] | undefined = undefined;
  let frame_index: number | undefined = undefined;

  if (object.is_type(BaseSchema.BBox)) {
    const box = object as BBox;
    coords = box.data.coords;
    frame_index = box.ui.frame_index;
  } else if (object.is_type(BaseSchema.Mask)) {
    const mask = object as Mask;
    if (mask.ui.bounds) {
      const b = mask.ui.bounds;
      coords = [b.x, b.y, b.width, b.height];
    }
    frame_index = mask.ui.frame_index;
  }

  const view_name = object.data.view_name;
  if (!coords || !view_name || !metas) return null;
  if (!(view_name in views)) return null;
  const candidateView = views[view_name];
  if (!candidateView) return null;

  const viewData =
    metas.type === WorkspaceType.VIDEO
      ? (() => {
          if (frame_index === undefined || !Array.isArray(candidateView)) return null;
          const frame = candidateView[frame_index];
          return frame?.data ?? null;
        })()
      : (() => {
          if (Array.isArray(candidateView)) return null;
          return candidateView.data;
        })();

  if (!viewData?.url) return null;
  if (viewData.width === undefined || viewData.height === undefined) return null;

  if (object.is_type(BaseSchema.Mask) || !(object as BBox).data.is_normalized) {
    coords = [
      coords[0] / viewData.width,
      coords[1] / viewData.height,
      coords[2] / viewData.width,
      coords[3] / viewData.height,
    ];
  }
  return {
    baseImageDimensions: {
      width: viewData.width,
      height: viewData.height,
    },
    coords,
    uri: viewData.url,
    view: view_name,
  };
};

const getFirstTrackFrame = (entity: Entity): number => {
  return entity.ui.childs && entity.ui.childs.length > 0
    ? Math.min(
        ...entity.ui.childs
          .filter((ann) => ann.is_type(BaseSchema.Tracklet))
          .map((trk) => (trk as Tracklet).data.start_frame),
      )
    : Infinity;
};

export const sortEntities = (a: Entity, b: Entity): number => {
  let result = 0;
  if (entityHasTracklets(a) && entityHasTracklets(b)) {
    result = getFirstTrackFrame(a) - getFirstTrackFrame(b);
  }
  if (result === 0 && "name" in a.data && "name" in b.data) {
    result = (a.data["name"] as string).localeCompare(b.data["name"] as string);
  }
  if (result === 0) {
    result = a.id.localeCompare(b.id);
  }
  return result;
};
