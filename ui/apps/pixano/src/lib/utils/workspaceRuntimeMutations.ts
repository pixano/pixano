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
  itemMetas,
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
 * Puts a record, as the workspace loader returns it, in the workspace stores, in place of the
 * previous record and of the changes not saved yet.
 */
export function commitLoadedWorkspace(
  workspaceData: WorkspaceData,
  featureValues: FeaturesValues,
): void {
  // Another item: nothing of the previous one stays in edit mode.
  clearTrackEditing();
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
