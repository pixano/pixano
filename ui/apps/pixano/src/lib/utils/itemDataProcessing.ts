/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { fpsFromSequenceFrames } from "$lib/timeline/timeFormat";
import {
  Annotation,
  BaseSchema,
  Entity,
  initDisplayControl,
  isSequenceFrameArray,
  WorkspaceType,
  type FeaturesValues,
  type SequenceFrame,
  type View,
} from "$lib/types/dataset";
import type { WorkspaceData } from "$lib/types/workspace";
import { sortByFrameIndex } from "$lib/utils/videoUtils";
import { normalizeWorkspaceRuntimeState } from "$lib/utils/workspaceRuntime";

/**
 * Prepare a single annotation for front-end display.
 * Unpacks mask RLE, generates SVG polygons, and attaches frame indices for video.
 */
function prepareAnnotation(ann: Annotation, workspaceType: WorkspaceType): Annotation {
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
  const newEntities: Entity[] = [];

  for (const itemEntities of Object.values(entitiesByTable)) {
    for (const entity of itemEntities) {
      entity.ui = { ...entity.ui, childs: entity.ui.childs ?? [] };
      newEntities.push(entity);
    }
  }

  return newEntities;
}

/** The frames of the first sequence view: the playback rate is read from them. */
function firstSequenceFrames(views: Record<string, View | View[]>): SequenceFrame[] | undefined {
  for (const view in views) {
    const frames = views[view];
    if (isSequenceFrameArray(frames)) return frames;
  }
  return undefined;
}

/**
 * The frame rate, from the stored frame timestamps (seconds, stamped at import as
 * frame_index / fps). Undefined when the rate cannot be known: fewer than two frames,
 * or timestamps all zero (fps-unknown imports).
 */
export function computeWorkspaceVideoFps(views: Record<string, View | View[]>): number | undefined {
  const frames = firstSequenceFrames(views);
  return frames ? fpsFromSequenceFrames(frames) : undefined;
}

/**
 * The playback interval in MILLISECONDS per frame, from the frame rate. Undefined when
 * the rate cannot be known, so the caller uses the playback default instead of racing at
 * setInterval(0).
 */
export function computeWorkspaceVideoSpeed(
  views: Record<string, View | View[]>,
): number | undefined {
  const fps = computeWorkspaceVideoFps(views);
  return fps === undefined ? undefined : Math.max(1, Math.round(1000 / fps));
}

export interface WorkspaceRuntimeData {
  annotations: Annotation[];
  entities: Entity[];
  videoSpeed: number | undefined;
  videoFps: number | undefined;
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

  const videoFps = computeWorkspaceVideoFps(workspaceData.views);

  // Prepare all annotations
  const newAnns: Annotation[] = [];
  for (const anns of Object.values(workspaceData.annotations)) {
    for (const ann of anns) {
      newAnns.push(prepareAnnotation(ann, workspaceType));
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
    videoSpeed: videoFps === undefined ? undefined : Math.max(1, Math.round(1000 / videoFps)),
    videoFps,
  };
}

export const processWorkspaceRecord = buildWorkspaceRuntimeData;
