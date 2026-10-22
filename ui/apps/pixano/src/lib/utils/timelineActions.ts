/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * What a click on the video timeline does to the workspace. Every entry point goes through
 * the timeline policy (lib/timeline/timelineInteraction.ts), so a click never cancels a
 * drawing session and never moves the shape of an open save form to another frame.
 */

import {
  timelineActiveCamera,
  timelineAddInViewTarget,
  timelineFocusedRowId,
  timelineSelectedEntityId,
} from "$lib/stores/timelineInspectorStore.svelte";
import { isTrackingByDetectionActive } from "$lib/stores/trackingByDetectionStore.svelte";
import { isTracking, isVosSessionActive } from "$lib/stores/trackingStore.svelte";
import { currentFrameIndex, lastFrameIndex, playbackState } from "$lib/stores/videoStores.svelte";
import { newShape, selectedTool } from "$lib/stores/workspaceStores.svelte";
import { timelinePolicy, type TimelinePolicy } from "$lib/timeline/timelineInteraction";
import { panTool, rectangleTool, ToolType } from "$lib/tools";
import { editModeBlockedReason } from "$lib/utils/editMode";
import { highlightEntity } from "$lib/utils/highlightOperations";
import { updateView } from "$lib/utils/videoOperations";

/** The timeline policy for the workspace as it is now. */
export function currentTimelinePolicy(): TimelinePolicy {
  return timelinePolicy({
    toolType: selectedTool.value?.type ?? ToolType.Pan,
    sessionActive:
      isTracking.value || isVosSessionActive.value || isTrackingByDetectionActive.value,
    saving: newShape.value.status === "saving",
    playing: playbackState.value.intervalId !== 0,
    blockedReason: editModeBlockedReason(),
  });
}

/** Move the playhead to `frame`, clamped to the clip; a no-op while the save form is open. */
export function seekTimeline(
  frame: number,
  policy: TimelinePolicy = currentTimelinePolicy(),
): void {
  if (!policy.seeks || !Number.isFinite(frame)) return;
  const target = Math.min(lastFrameIndex.value ?? 0, Math.max(0, Math.round(frame)));
  if (target === currentFrameIndex.value) return;
  currentFrameIndex.value = target;
  updateView(target);
}

/** Switch a drawing tool to Pan, where selection works, when no session would be lost. */
export function leaveDrawingTool(policy: TimelinePolicy = currentTimelinePolicy()): void {
  if (policy.leavesDrawingTool) selectedTool.value = panTool;
}

export interface TimelineRowTarget {
  /** The row's entity (a sub-entity has its own row). */
  rowId: string;
  /** Its top-level entity: the one the canvas and the inspector select. */
  topId: string;
}

/**
 * A row header click, like the old colored dot: select the row's object and bring the
 * playhead into its tracks (`entryFrame`), or deselect it when its row is the selected one.
 * During a session only the inspector card opens and the playhead moves.
 */
export function activateTimelineRow(
  row: TimelineRowTarget,
  { selected, entryFrame }: { selected: boolean; entryFrame: number | null },
  policy: TimelinePolicy = currentTimelinePolicy(),
): void {
  if (!policy.seeks) return;
  leaveDrawingTool(policy);
  highlightEntity(row.topId, selected, true);
  if (policy.selects) timelineFocusedRowId.value = selected ? null : row.rowId;
  if (!selected && entryFrame !== null) seekTimeline(entryFrame, policy);
}

/**
 * A click on a keyframe tick: select its object (never deselect) and land on the exact frame.
 * Under Fusion and during a session the click only moves the playhead.
 */
export function selectTimelineKeyframe(
  row: TimelineRowTarget,
  frame: number,
  policy: TimelinePolicy = currentTimelinePolicy(),
): void {
  if (!policy.seeks) return;
  if (policy.selects && selectedTool.value?.type !== ToolType.Fusion) {
    leaveDrawingTool(policy);
    if (timelineSelectedEntityId.value !== row.topId) highlightEntity(row.topId, false, true);
    timelineFocusedRowId.value = row.rowId;
  }
  seekTimeline(frame, policy);
}

/**
 * A camera sub-row click: that camera becomes the active one, and the row is selected (never
 * deselected), with the playhead brought into the camera's tracks.
 */
export function activateTimelineCamera(
  row: TimelineRowTarget,
  view: string,
  entryFrame: number | null,
  policy: TimelinePolicy = currentTimelinePolicy(),
): void {
  timelineActiveCamera.value = view;
  activateTimelineRow(row, { selected: false, entryFrame }, policy);
}

/**
 * "+ Add in this view": select the object, make the camera active and pick the box tool, so
 * the next box drawn in that camera can be saved to the object (the save form preselects it).
 * Returns false when a session or the save form is in the way.
 */
export function armAddInView(row: TimelineRowTarget, view: string): boolean {
  if (editModeBlockedReason() !== null || newShape.value.status === "saving") return false;
  // Selection only works under Pan: select first, then pick the box tool.
  if (selectedTool.value?.type !== ToolType.Pan) selectedTool.value = panTool;
  if (timelineSelectedEntityId.value !== row.topId) highlightEntity(row.topId, false, true);
  timelineFocusedRowId.value = row.rowId;
  timelineActiveCamera.value = view;
  timelineAddInViewTarget.value = { entityId: row.rowId, viewName: view };
  selectedTool.value = rectangleTool;
  return true;
}
