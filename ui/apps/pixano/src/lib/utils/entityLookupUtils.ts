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
  type MultiPath,
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
export const tryGetTopEntityFromList = (
  obj: Annotation | Entity,
  entitiesList: Entity[],
): Entity | null => {
  let entity: Entity | undefined;
  if (obj.table_info.group === "entities") {
    entity = obj as Entity;
    while (entity && entity.data.parent_id !== "") {
      entity = entitiesList.find(
        (parent_entity) => entity && parent_entity.id === entity.data.parent_id,
      );
    }
    if (!entity) {
      return null;
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
      return null;
    }
    ann.ui.top_entities.unshift(entity);
  }
  return entity;
};

export const getTopEntityFromList = (obj: Annotation | Entity, entitiesList: Entity[]): Entity => {
  const entity = tryGetTopEntityFromList(obj, entitiesList);
  if (!entity) {
    if (obj.table_info.group === "entities") {
      console.error("ERROR: Unable to find top level Entity of entity", obj);
      throw new Error(`ERROR: Unable to find top level Entity of entity (id=${obj.id})`);
    }
    console.error("ERROR: Unable to find top level Entity of annotation", obj);
    throw new Error(`ERROR: Unable to find top level Entity of annotation (id=${obj.id})`);
  }
  return entity;
};

export const getTopEntity = (obj: Annotation | Entity): Entity => {
  return getTopEntityFromList(obj, entities.value);
};

export const tryGetTopEntity = (obj: Annotation | Entity): Entity | null => {
  return tryGetTopEntityFromList(obj, entities.value);
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

/**
 * Canonical fallback table names for annotation types that may not exist
 * yet in the dataset schema.  When the first annotation of a new type is
 * created, the backend will auto-create the table with the base schema.
 */
const CANONICAL_TABLE_FALLBACKS: Partial<Record<BaseSchema, string>> = {
  [BaseSchema.MultiPath]: "multi_paths",
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
  const canonical = CANONICAL_TABLE_FALLBACKS[baseSchema];
  if (canonical) {
    return canonical;
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
  } else if (object.is_type(BaseSchema.MultiPath)) {
    const mp = object as MultiPath;
    const c = mp.data.coords;
    if (c && c.length >= 4) {
      let minX = Infinity,
        minY = Infinity,
        maxX = -Infinity,
        maxY = -Infinity;
      for (let i = 0; i < c.length; i += 2) {
        if (c[i] < minX) minX = c[i];
        if (c[i + 1] < minY) minY = c[i + 1];
        if (c[i] > maxX) maxX = c[i];
        if (c[i + 1] > maxY) maxY = c[i + 1];
      }
      // Coords are already normalised [0, 1]
      coords = [minX, minY, maxX - minX, maxY - minY];
    }
    frame_index = mp.ui.frame_index;
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

  // Normalise pixel-space coords to [0, 1].  MultiPath coords are already normalised.
  const needsNormalisation =
    object.is_type(BaseSchema.Mask) ||
    (object.is_type(BaseSchema.BBox) && !(object as BBox).data.is_normalized);
  if (needsNormalisation) {
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
