/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  Annotation,
  BaseSchema,
  Entity,
  initDisplayControl,
  isSequenceFrameArray,
  WorkspaceType,
  type FeaturesValues,
  type View,
} from "$lib/types/dataset";
import type { WorkspaceData } from "$lib/types/workspace";
import { normalizeWorkspaceRuntimeState } from "$lib/utils/workspaceRuntime";
import { sortByFrameIndex } from "$lib/utils/videoUtils";

/**
 * Prepare a single annotation for front-end display.
 * Unpacks mask RLE, generates SVG polygons, and attaches frame indices for video.
 */
function prepareAnnotation(
  ann: Annotation,
  workspaceType: WorkspaceType,
  views: Record<string, View | View[]>,
): Annotation {
  ann.ui = { datasetItemType: workspaceType, displayControl: initDisplayControl };

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

function flattenWorkspaceEntities(entitiesByTable: WorkspaceData["entities"]): Entity[] {
  let newEntities: Entity[] = [];

  for (const itemEntities of Object.values(entitiesByTable)) {
    for (const entity of itemEntities) {
      entity.ui = { ...entity.ui, childs: entity.ui.childs ?? [] };
      newEntities.push(entity);
    }
  }

  return newEntities;
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

  const entities = flattenWorkspaceEntities(workspaceData.entities);
  const normalized = normalizeWorkspaceRuntimeState(
    {
      annotations: newAnns,
      entities,
    },
    workspaceType,
    workspaceData.views,
  );

  return {
    annotations: normalized.annotations,
    entities: normalized.entities,
    videoSpeed,
  };
}

export const processWorkspaceRecord = buildWorkspaceRuntimeData;
