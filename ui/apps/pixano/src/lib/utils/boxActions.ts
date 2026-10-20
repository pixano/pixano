/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Contextual actions of a box, offered by its chip's "…" menu on the canvas. Every action
 * stages the changes it makes (saveTo), so they persist on the next save.
 */

import {
  trackFrameActions,
  trackletIdOfShape,
  trackletTopEntityId,
  type ShapeLike,
} from "$lib/stores/trackEditing";
import { currentFrameIndex } from "$lib/stores/videoStores.svelte";
import {
  annotations,
  current_itemBBoxes,
  current_itemKeypoints,
  entities,
  mediaViews,
  trackletIdByChildId,
} from "$lib/stores/workspaceStores.svelte";
import type { BoxAction } from "$lib/types/boxActions";
import {
  BaseSchema,
  type Annotation,
  type BBox,
  type Entity,
  type Tracklet,
} from "$lib/types/dataset";
import type { KeypointAnnotation } from "$lib/types/shapeTypes";
import { editTrack, exitEditMode, isTrackEditing } from "$lib/utils/editMode";
import { deleteEntity, onDeleteTrackItemClick } from "$lib/utils/entityDeletion";
import { tryGetTopEntity } from "$lib/utils/entityLookupUtils";
import { clearHighlighting } from "$lib/utils/highlightOperations";
import { addKeyItemToTracklet, splitTrackletAfter } from "$lib/utils/trackletOperations";

function findEntity(entityId: string | undefined): Entity | undefined {
  return entityId === undefined
    ? undefined
    : entities.value.find((entity) => entity.id === entityId);
}

/** Delete `child` of `entity` (a track, a box); once the entity is gone, drop its focus. */
function deleteChild(entity: Entity, child: Annotation): void {
  deleteEntity(entity, child);
  if (!entities.value.some((candidate) => candidate.id === entity.id)) clearHighlighting();
}

function deleteBoxAction(box: ShapeLike): BoxAction[] {
  const stored = annotations.value.find((annotation) => annotation.id === box.id);
  const entity = stored ? (tryGetTopEntity(stored) ?? undefined) : undefined;
  if (!stored || !entity) return [];
  return [
    {
      id: "delete-box",
      label: "Delete box",
      destructive: true,
      confirmLabel: "Click again to delete the box",
      run: () => {
        if (stored.ui.displayControl.editing) exitEditMode();
        deleteChild(entity, stored);
      },
    },
  ];
}

/** Actions for a box of an image, or of a video outside every track. */
export function imageBoxActions(box: BBox): BoxAction[] {
  return deleteBoxAction(box);
}

/** The interpolated shapes a track shows on a frame, from which a keyframe can be added there. */
export interface TrackGhosts {
  bboxes: BBox[];
  keypoints: KeypointAnnotation[];
}

/**
 * The keyframe, split and delete actions of a track on `frame`. `here` words them for the
 * canvas chip (the current frame); otherwise they name the frame, for the timeline menu.
 * "Add a keyframe" is offered only with `ghosts`, the interpolated shapes shown on that frame.
 */
export function trackActionsAt(
  tracklet: Tracklet,
  entity: Entity,
  frame: number,
  { here = false, ghosts }: { here?: boolean; ghosts?: TrackGhosts } = {},
): BoxAction[] {
  const can = trackFrameActions(tracklet, frame);
  const actions: BoxAction[] = [];
  if (can.canAddKeyframe && ghosts) {
    actions.push({
      id: "add-keyframe",
      label: here ? "Add a keyframe here" : `Add a keyframe at #${frame}`,
      run: () => {
        const added = addKeyItemToTracklet(
          tracklet,
          entity,
          mediaViews.value,
          ghosts.bboxes,
          ghosts.keypoints,
          frame,
        );
        if (added) editTrack(tracklet.id, { reveal: false });
      },
    });
  }
  if (can.canRemoveKeyframe) {
    actions.push({
      id: "remove-keyframe",
      label: here ? "Remove this keyframe" : `Remove keyframe #${frame}`,
      destructive: true,
      confirmLabel: "Click again to remove the keyframe",
      run: () => onDeleteTrackItemClick(tracklet, frame),
    });
  }
  if (can.canSplit) {
    actions.push({
      id: "split-track",
      label: here ? "Split the track after this frame" : `Split after #${frame}`,
      run: () => {
        splitTrackletAfter(tracklet, entity, frame, mediaViews.value);
      },
    });
  }
  // deleteEntity removes the whole object when the track and its keyframes are all it has.
  const trackChildIds = new Set([tracklet.id, ...tracklet.ui.childs.map((child) => child.id)]);
  const deletesObject = (entity.ui.childs ?? []).every((child) => trackChildIds.has(child.id));
  actions.push({
    id: "delete-track",
    label: deletesObject ? "Delete the object" : "Delete the track",
    destructive: true,
    confirmLabel: deletesObject
      ? "Click again to delete the object"
      : "Click again to delete the track",
    run: () => {
      if (isTrackEditing(tracklet.id)) exitEditMode();
      deleteChild(entity, tracklet);
    },
  });
  return actions;
}

/** Actions for a video box: keyframe, split and delete for a track's box. */
export function videoBoxActions(box: BBox): BoxAction[] {
  const trackletId = trackletIdOfShape(box, trackletIdByChildId.value);
  if (trackletId === undefined) return deleteBoxAction(box);
  const tracklet = annotations.value.find(
    (annotation) => annotation.id === trackletId && annotation.is_type(BaseSchema.Tracklet),
  ) as Tracklet | undefined;
  const entity = tracklet ? findEntity(trackletTopEntityId(tracklet)) : undefined;
  if (!tracklet || !entity) return [];

  // A keyframe can be added from the box shown here only when it is an interpolated ghost.
  const ghosts = box.ui.startRef
    ? { bboxes: current_itemBBoxes.value, keypoints: current_itemKeypoints.value }
    : undefined;
  return trackActionsAt(tracklet, entity, currentFrameIndex.value, { here: true, ghosts });
}
