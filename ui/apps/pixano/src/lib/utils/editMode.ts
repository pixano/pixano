/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Edit mode: which shape the user is reshaping, and the actions that enter and leave it.
 *
 * There is one edit target at a time. In a video, a shape that belongs to a track puts
 * the whole track in edit mode (`editedTrackletId`): its shape on every frame, keyframe
 * or interpolated, is the editable one, so edit mode follows the track as the user steps
 * through frames. A shape outside every track (images, untracked video annotations) is
 * edited through its own stored `editing` flag. Entering edit mode focuses the target's
 * entity and switches to the Pan tool, which frame stepping and dragging need.
 */

import {
  isPreviewShape,
  pickEntityEditShape,
  shapeTopEntityId,
  trackletIdOfShape,
  trackletTopEntityId,
  type ShapeLike,
} from "$lib/stores/trackEditing";
import { isTrackingByDetectionActive } from "$lib/stores/trackingByDetectionStore.svelte";
import { isTracking, isVosSessionActive } from "$lib/stores/trackingStore.svelte";
import {
  annotations,
  clearTrackEditing,
  editedTrackletId,
  highlightedEntity,
  mediaViews,
  selectedTool,
  trackletIdByChildId,
} from "$lib/stores/workspaceStores.svelte";
import { panTool, ToolType } from "$lib/tools";
import { BaseSchema, type Annotation, type Tracklet } from "$lib/types/dataset";
import { updateDisplayControl } from "$lib/utils/displayControl";
import { tryGetTopEntity } from "$lib/utils/entityLookupUtils";
import { highlightEntity } from "$lib/utils/highlightOperations";

export type EditModeOptions = {
  /** Open the entity's inspector card and scroll it and its timeline row into view. */
  reveal?: boolean;
};

/**
 * Why existing shapes cannot be edited right now, or null when they can. A tracking
 * session turns every box edit into a keyframe of the track being drawn, and leaving
 * the drawing tool would end a session, so edit mode waits for sessions to finish.
 */
export function editModeBlockedReason(): string | null {
  if (isTracking.value) return "Finish or cancel the tracking session first";
  if (isVosSessionActive.value) return "Finish or cancel the mask tracking session first";
  if (isTrackingByDetectionActive.value) return "Finish the detection review first";
  if (selectedTool.value?.type === ToolType.Fusion) return "Leave association mode first";
  return null;
}

function findTracklet(trackletId: string): Tracklet | undefined {
  return annotations.value.find(
    (annotation) => annotation.id === trackletId && annotation.is_type(BaseSchema.Tracklet),
  ) as Tracklet | undefined;
}

function annotationTopEntityId(annotation: Annotation): string | undefined {
  return tryGetTopEntity(annotation)?.id ?? shapeTopEntityId(annotation);
}

function usePanTool(): void {
  if (selectedTool.value?.type !== ToolType.Pan) selectedTool.value = panTool;
}

function focusEntity(entityId: string | undefined, reveal: boolean): void {
  if (entityId === undefined || highlightedEntity.value === entityId) return;
  highlightEntity(entityId, false, reveal);
}

/** Turn off the stored editing flag of every annotation but `keepId`; true when one changed. */
function setStoredEditing(keepId: string | null): boolean {
  const needsChange = annotations.value.some(
    (annotation) => (annotation.ui.displayControl.editing ?? false) !== (annotation.id === keepId),
  );
  if (!needsChange) return false;
  annotations.update((current) =>
    current.map((annotation) =>
      updateDisplayControl(annotation, { editing: annotation.id === keepId }),
    ),
  );
  return true;
}

/** Put a track in edit mode; returns false when edit mode is blocked or the track is gone. */
export function editTrack(trackletId: string, { reveal = true }: EditModeOptions = {}): boolean {
  if (editModeBlockedReason() !== null) return false;
  const tracklet = findTracklet(trackletId);
  if (!tracklet) return false;
  usePanTool();
  focusEntity(trackletTopEntityId(tracklet), reveal);
  setStoredEditing(null);
  editedTrackletId.value = trackletId;
  return true;
}

/** Put one annotation outside every track in edit mode. */
export function editAnnotation(
  annotation: Annotation,
  { reveal = true }: EditModeOptions = {},
): boolean {
  if (editModeBlockedReason() !== null) return false;
  usePanTool();
  focusEntity(annotationTopEntityId(annotation), reveal);
  clearTrackEditing();
  setStoredEditing(annotation.id);
  return true;
}

/** Leave edit mode, whatever is being edited; returns whether something was. */
export function exitEditMode(): boolean {
  const wasEditingTrack = editedTrackletId.value !== null;
  clearTrackEditing();
  const wasEditingAnnotation = setStoredEditing(null);
  return wasEditingTrack || wasEditingAnnotation;
}

export function isTrackEditing(trackletId: string): boolean {
  return editedTrackletId.value === trackletId;
}

/**
 * Enter edit mode on a displayed shape: its track when it belongs to one, the stored
 * annotation otherwise. Returns false for previews, unknown shapes and blocked modes,
 * so callers can fall back to a plain selection.
 */
export function enterEditMode(shape: ShapeLike, options: EditModeOptions = {}): boolean {
  if (isPreviewShape(shape)) return false;
  const trackletId = trackletIdOfShape(shape, trackletIdByChildId.value);
  if (trackletId !== undefined) return editTrack(trackletId, options);
  const stored = annotations.value.find((annotation) => annotation.id === shape.id);
  return stored ? editAnnotation(stored, options) : false;
}

/** Leave edit mode when `shape` is the one being edited, enter it otherwise. */
export function toggleEditMode(shape: ShapeLike, options: EditModeOptions = {}): boolean {
  if (shape.ui?.displayControl.editing) {
    exitEditMode();
    return true;
  }
  return enterEditMode(shape, options);
}

export function toggleEditTrack(trackletId: string, options: EditModeOptions = {}): boolean {
  if (isTrackEditing(trackletId)) {
    exitEditMode();
    return true;
  }
  return editTrack(trackletId, options);
}

/** Toggle edit mode from a stored annotation: its track when it has one. */
export function toggleEditAnnotation(
  annotation: Annotation,
  options: EditModeOptions = {},
): boolean {
  const trackletId = annotation.is_type(BaseSchema.Tracklet)
    ? annotation.id
    : trackletIdByChildId.value.get(annotation.id);
  if (trackletId !== undefined) return toggleEditTrack(trackletId, options);
  if (annotation.ui.displayControl.editing) {
    exitEditMode();
    return true;
  }
  return editAnnotation(annotation, options);
}

/** Whether one of `entityId`'s tracks or annotations is in edit mode. */
export function isEntityEditing(entityId: string): boolean {
  const trackletId = editedTrackletId.value;
  if (trackletId !== null) {
    const tracklet = findTracklet(trackletId);
    return tracklet !== undefined && trackletTopEntityId(tracklet) === entityId;
  }
  return annotations.value.some(
    (annotation) =>
      annotation.ui.displayControl.editing && annotationTopEntityId(annotation) === entityId,
  );
}

/**
 * Toggle edit mode for an entity on the current frame (timeline pencil, E key): leave it
 * when the entity is being edited, else edit its shape among `shapes`, preferring
 * `preferredView`, then the media view order.
 */
export function toggleEditModeForEntity(
  entityId: string,
  shapes: ReadonlyArray<ShapeLike>,
  { preferredView, ...options }: EditModeOptions & { preferredView?: string } = {},
): boolean {
  if (isEntityEditing(entityId)) {
    exitEditMode();
    return true;
  }
  const viewOrder = Object.keys(mediaViews.value);
  const shape = pickEntityEditShape(shapes, entityId, viewOrder, preferredView);
  return shape ? enterEditMode(shape, options) : false;
}
