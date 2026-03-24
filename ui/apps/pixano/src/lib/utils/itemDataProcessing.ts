/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  Annotation,
  BaseSchema,
  Entity,
  entityHasTracklets,
  initDisplayControl,
  isSequenceFrameArray,
  Mask,
  Tracklet,
  WorkspaceType,
  type FeaturesValues,
  type View,
} from "$lib/types/dataset";
import type { WorkspaceData } from "$lib/types/workspace";
import {
  resolveMaskBitmapSource,
  resolveMaskBounds,
  rleCountsToBounds,
  rleFrString,
} from "$lib/utils/maskUtils";
import { sortByFrameIndex } from "$lib/utils/videoUtils";

/**
 * Prepare a single annotation for front-end display.
 * Unpacks mask RLE, generates SVG polygons, and attaches frame indices for video.
 */
function prepareAnnotation(
  ann: Annotation,
  workspaceType: WorkspaceType,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  views: Record<string, View | View[]>,
): Annotation {
  ann.ui = { datasetItemType: workspaceType, displayControl: initDisplayControl };

  if (ann.table_info.base_schema === BaseSchema.Mask) {
    const mask: Mask = ann as Mask;
    // Prefer backend-provided URL/bounds and avoid eager bitmap materialization at item load.
    if (!mask.ui.bitmapUrl) {
      mask.ui.bitmapUrl =
        resolveMaskBitmapSource({ data: mask.data, metadata: mask.data.inference_metadata }) ??
        undefined;
    }
    if (!mask.ui.bounds) {
      mask.ui.bounds =
        resolveMaskBounds({ data: mask.data, metadata: mask.data.inference_metadata }) ?? undefined;
    }

    // Fallback: infer bounds from RLE counts only when metadata bounds are absent.
    // This is much cheaper than decoding + scanning a full RGBA bitmap.
    if (!mask.ui.bounds) {
      if (typeof mask.data.counts === "string") {
        mask.data.counts = rleFrString(mask.data.counts);
      }
      if (Array.isArray(mask.data.counts) && mask.data.size.length >= 2) {
        const h = mask.data.size[0];
        const w = mask.data.size[1];
        if (Number.isFinite(h) && Number.isFinite(w) && h > 0 && w > 0) {
          mask.ui.bounds = rleCountsToBounds(mask.data.counts, [h, w]) ?? undefined;
        }
      }
    }
  }

  if (workspaceType === WorkspaceType.VIDEO) {
    if (ann.table_info.base_schema !== BaseSchema.Tracklet) {
      const frameIndex = ann.data.frame_index as number | undefined;
      if (typeof frameIndex === "number" && frameIndex >= 0) {
        ann.ui.frame_index = frameIndex;
      }
    }
  }

  return ann;
}

/**
 * Build entity hierarchy: attach child annotations to entities, and gather
 * sub-entity children for parent tracks.
 */
export function buildWorkspaceEntities(
  entitiesByTable: WorkspaceData["entities"],
  processedAnnotations: Annotation[],
): Entity[] {
  let newEntities: Entity[] = [];
  const subEntitiesChilds: Record<string, Annotation[]> = {};

  for (const itemEntities of Object.values(entitiesByTable)) {
    for (const entity of itemEntities) {
      entity.ui = {
        ...entity.ui,
        childs: processedAnnotations.filter((ann) => ann.data.entity_id === entity.id),
      };
      newEntities.push(entity);
      if (entity.data.parent_id !== "" && entity.ui.childs) {
        if (entity.data.parent_id in subEntitiesChilds) {
          subEntitiesChilds[entity.data.parent_id] = subEntitiesChilds[
            entity.data.parent_id
          ].concat(entity.ui.childs);
        } else {
          subEntitiesChilds[entity.data.parent_id] = entity.ui.childs;
        }
      }
    }
  }

  if (Object.keys(subEntitiesChilds).length > 0) {
    newEntities = newEntities.map((entity) => {
      if (entityHasTracklets(entity) && entity.id in subEntitiesChilds) {
        entity.ui.childs = [...entity.ui.childs, ...subEntitiesChilds[entity.id]];
      }
      return entity;
    });
  }

  return newEntities;
}

/**
 * Attach tracklet children and top entities to annotations.
 * Must be called after entities are set in the store (uses getTopEntity which reads the store).
 */
export function attachTrackChildren(
  anns: Annotation[],
  getTopEntity: (ann: Annotation) => Entity,
): Annotation[] {
  return anns.map((ann) => {
    if (ann.is_type(BaseSchema.Tracklet)) {
      const topEntity = getTopEntity(ann);
      const track = ann as Tracklet;
      if (topEntity) {
        track.ui.childs =
          topEntity.ui.childs?.filter(
            (child) =>
              child.ui.frame_index !== undefined &&
              child.ui.frame_index <= track.data.end_frame &&
              child.ui.frame_index >= track.data.start_frame &&
              child.data.view_id === track.data.view_id,
          ) || [];
        track.ui.childs.sort((a, b) => a.ui.frame_index - b.ui.frame_index);
      }
    }
    return ann;
  });
}

/**
 * Compute video speed from views (time between frames).
 */
export function computeWorkspaceVideoSpeed(
  views: Record<string, View | View[]>,
): number | undefined {
  for (const view in views) {
    if (isSequenceFrameArray(views[view])) {
      const video = views[view];
      return Math.round(
        (video[video.length - 1].data.timestamp - video[0].data.timestamp) / video.length,
      );
    }
  }
  return undefined;
}

export interface WorkspaceRuntimeData {
  annotations: Annotation[];
  entities: Entity[];
  videoSpeed: number | undefined;
}

/**
 * Top-level orchestrator: processes workspace data into front-end-ready runtime data.
 * Pure function — no store mutations.
 */
export function buildWorkspaceRuntimeData(
  workspaceData: WorkspaceData,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  featureValues: FeaturesValues,
): WorkspaceRuntimeData {
  const workspaceType = workspaceData.ui.type;

  // Compute video speed
  const videoSpeed = computeWorkspaceVideoSpeed(workspaceData.views);

  // Prepare all annotations
  const newAnns: Annotation[] = [];
  for (const anns of Object.values(workspaceData.annotations)) {
    for (const ann of anns) {
      newAnns.push(prepareAnnotation(ann, workspaceType, workspaceData.views));
    }
  }

  // Sort by frame_index
  newAnns.sort((a, b) => sortByFrameIndex(a, b));

  // Build entity hierarchy
  const entities = buildWorkspaceEntities(workspaceData.entities, newAnns);

  return {
    annotations: newAnns,
    entities,
    videoSpeed,
  };
}

export const processWorkspaceRecord = buildWorkspaceRuntimeData;
