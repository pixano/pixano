/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { DEFAULT_VIDEO_SPEED_MS, playbackState, videoFps } from "$lib/stores/videoStores.svelte";
import {
  annotations,
  clearTrackEditing,
  entities,
  highlightedEntity,
  itemMetas,
  reviewedAnnotation,
  views,
  workspaceSaveQueue,
} from "$lib/stores/workspaceStores.svelte";
import {
  WorkspaceType,
  type Annotation,
  type Entity,
  type FeaturesValues,
} from "$lib/types/dataset";
import type { WorkspaceData } from "$lib/types/workspace";
import { buildWorkspaceRuntimeData } from "$lib/utils/itemDataProcessing";
import { normalizeWorkspaceRuntimeState } from "$lib/utils/workspaceRuntime";

export function commitNormalizedWorkspaceRuntime(
  nextAnnotations: Annotation[],
  nextEntities: Entity[],
): { annotations: Annotation[]; entities: Entity[] } {
  const workspaceType = itemMetas.value?.type ?? WorkspaceType.UNDEFINED;
  const normalized = normalizeWorkspaceRuntimeState(
    {
      annotations: nextAnnotations,
      entities: nextEntities,
    },
    workspaceType,
    views.value,
  );
  annotations.value = normalized.annotations;
  entities.value = normalized.entities;
  return normalized;
}

/**
 * Takes off the screen an annotation the dataset no longer holds, as a save found it: deleted
 * since the record opened, or replaced by a model's run. Nothing is staged: it is gone already.
 */
export function forgetGoneAnnotation(id: string): void {
  const kept = annotations.value.filter((annotation) => annotation.id !== id);
  if (kept.length === annotations.value.length) return;
  commitNormalizedWorkspaceRuntime(kept, entities.value);
}

/**
 * Puts a record, as the workspace loader returns it, in the workspace stores, in place of the
 * previous record and of the changes not saved yet.
 */
export function commitLoadedWorkspace(
  workspaceData: WorkspaceData,
  featureValues: FeaturesValues,
): void {
  // Another item: nothing of the previous one stays in edit mode, nor focused, nor under review —
  // naming no object here, its focus would fade every annotation of the record opened, and the
  // annotation under review hide them.
  clearTrackEditing();
  highlightedEntity.value = null;
  reviewedAnnotation.value = null;
  workspaceSaveQueue.reset();
  views.value = workspaceData.views;

  const result = buildWorkspaceRuntimeData(workspaceData, featureValues);

  // A record without frame timestamps plays at the default rate, not at the last one's.
  playbackState.update((old) => ({
    ...old,
    videoSpeed: result.videoSpeed ?? DEFAULT_VIDEO_SPEED_MS,
  }));
  videoFps.value = result.videoFps ?? null;

  entities.value = result.entities;
  annotations.value = result.annotations;

  itemMetas.value = {
    featuresList: featureValues || { main: {}, objects: {} },
    item: workspaceData.item,
    type: workspaceData.ui.type,
  };
}
