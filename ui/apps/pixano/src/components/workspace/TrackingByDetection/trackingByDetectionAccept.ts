/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Accepting a tracking-by-detection review: the kept tracks become rows staged in the save queue
 * (entities first, then tracklets, then boxes, as the queue orders them), the workspace runtime
 * shows them at once, and the session closes. Persisting is the workspace's normal save.
 */

import {
  keptDetectionTracks,
  resetTrackingByDetectionSession,
  resolveTrackingFrameSources,
  trackingByDetectionSession,
} from "$lib/stores/trackingByDetectionStore.svelte";
import { annotations, entities } from "$lib/stores/workspaceStores.svelte";
import { buildTrackingByDetectionRows } from "$lib/tracking/trackingByDetectionRows";
import type { FeaturesValues } from "$lib/types/dataset";
import { addNewInput } from "$lib/utils/featureMapping";
import { saveTo } from "$lib/utils/saveItemUtils";
import { resolveEntityLabelField } from "$lib/utils/workspaceDefaultFeatures";
import { commitNormalizedWorkspaceRuntime } from "$lib/utils/workspaceRuntimeMutations";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

export interface AcceptTrackingByDetectionInput {
  manifest: WorkspaceManifest;
  featureValues: FeaturesValues | undefined;
}

export interface AcceptedTrackingByDetection {
  entities: number;
  tracklets: number;
  bboxes: number;
  /** The entity field that received the class, if the table has one. */
  labelField: string | null;
}

/** The entity field that holds the object label in this dataset, if any. */
export function resolveWorkspaceLabelField(manifest: WorkspaceManifest): string | null {
  const entityTable = manifest.tablesByGroup.entities[0];
  if (!entityTable) return null;
  return resolveEntityLabelField(Object.keys(manifest.tablesByName[entityTable]?.fields ?? {}));
}

export function acceptTrackingByDetection(
  input: AcceptTrackingByDetectionInput,
): AcceptedTrackingByDetection | null {
  const state = trackingByDetectionSession.value;
  if (state.phase !== "review" || !state.viewName || !state.run || !state.target) return null;
  const sources = resolveTrackingFrameSources(state.viewName);
  const firstFrame = sources[0];
  if (!firstFrame) return null;

  const labelField = resolveWorkspaceLabelField(input.manifest);
  const rows = buildTrackingByDetectionRows({
    tracks: keptDetectionTracks.value,
    params: state.params,
    itemId: state.target.recordId,
    viewName: state.viewName,
    manifest: input.manifest,
    labelField,
    source: { modelName: state.run.model, providerName: state.run.providerName },
    frameSize: { width: firstFrame.width, height: firstFrame.height },
  });

  for (const entity of rows.entities) saveTo("add", entity);
  for (const tracklet of rows.tracklets) saveTo("add", tracklet);
  for (const bbox of rows.bboxes) saveTo("add", bbox);
  commitNormalizedWorkspaceRuntime(
    [...annotations.value, ...rows.tracklets, ...rows.bboxes],
    [...entities.value, ...rows.entities],
  );
  if (labelField) {
    for (const value of rows.classValues)
      addNewInput(input.featureValues, "objects", labelField, value);
  }
  resetTrackingByDetectionSession();

  return {
    entities: rows.entities.length,
    tracklets: rows.tracklets.length,
    bboxes: rows.bboxes.length,
    labelField,
  };
}
