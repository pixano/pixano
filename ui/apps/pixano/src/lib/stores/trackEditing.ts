/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Pure helpers for the track edit mode.
 *
 * One track at a time is in edit mode, and the shape it shows on the current frame,
 * stored keyframe or interpolated ghost, is the editable one: edit mode follows the
 * track from frame to frame. A track child's own stored `editing` flag does not count.
 * Shapes outside every track (images, untracked video annotations) keep their stored
 * flag. The reactive store (`editedTrackletId`) lives in workspaceBaseStores; the logic
 * sits here so it runs without the Svelte runtime.
 */

type ChildLike = { id: string; ui: { frame_index?: number } };

export type TrackLike = {
  id: string;
  data: { start_frame: number; end_frame: number; entity_id?: string; view_name?: string };
  ui: { childs?: ReadonlyArray<ChildLike>; top_entities?: ReadonlyArray<{ id: string }> };
};

/** A shape as displayed on the current frame: a box (with `data`) or keypoints. */
export type ShapeLike = {
  id: string;
  data?: { entity_id?: string; view_name?: string };
  viewRef?: { name: string };
  entityRef?: { id: string };
  table_info?: { name?: string };
  ui?: {
    startRef?: { id: string };
    displayControl: { editing?: boolean; hidden?: boolean };
    top_entities?: ReadonlyArray<{ id: string }>;
  };
};

/** Shapes drawn by a tracking session or a tracking-by-detection review. */
export const PREVIEW_TABLE_NAME = "_tracking_preview";

/** Map every track child's id to the id of its track. */
export function buildTrackletIdByChildId(tracklets: ReadonlyArray<TrackLike>): Map<string, string> {
  const map = new Map<string, string>();
  for (const tracklet of tracklets) {
    for (const child of tracklet.ui.childs ?? []) map.set(child.id, tracklet.id);
  }
  return map;
}

/**
 * The track a displayed shape belongs to: found through its own id for a stored
 * keyframe, through its start keyframe for an interpolated ghost (keypoint shapes have
 * no `data`, so the stored `tracklet_id` cannot be read from them).
 */
export function trackletIdOfShape(
  shape: ShapeLike,
  trackletIdByChildId: ReadonlyMap<string, string>,
): string | undefined {
  return trackletIdByChildId.get(shape.ui?.startRef?.id ?? shape.id);
}

/**
 * Mark the shapes of the edited track as editable and those of every other track as
 * not editable. `shapes` must be display copies: their display control is replaced,
 * never the stored annotation's.
 */
export function markTrackEditing<T extends ShapeLike>(
  shapes: T[],
  editedTrackletId: string | null,
  trackletIdByChildId: ReadonlyMap<string, string>,
): T[] {
  for (const shape of shapes) {
    if (!shape.ui) continue;
    const trackletId = trackletIdOfShape(shape, trackletIdByChildId);
    if (trackletId === undefined) continue;
    const editing = trackletId === editedTrackletId;
    if ((shape.ui.displayControl.editing ?? false) !== editing) {
      shape.ui.displayControl = { ...shape.ui.displayControl, editing };
    }
  }
  return shapes;
}

/** The entity a track belongs to. */
export function trackletTopEntityId(tracklet: TrackLike): string | undefined {
  return tracklet.ui.top_entities?.[0]?.id ?? tracklet.data.entity_id;
}

/** The entity a displayed shape belongs to. */
export function shapeTopEntityId(shape: ShapeLike): string | undefined {
  return shape.ui?.top_entities?.[0]?.id ?? shape.data?.entity_id ?? shape.entityRef?.id;
}

/** The view a displayed shape is drawn in. */
export function shapeViewName(shape: ShapeLike): string | undefined {
  return shape.data?.view_name ?? shape.viewRef?.name;
}

export function isPreviewShape(shape: ShapeLike): boolean {
  return shape.table_info?.name === PREVIEW_TABLE_NAME;
}

/**
 * The shape of `entityId` that edit mode opens on for the current frame: the one in
 * `preferredView` if any, else the first in view order. Ties keep the input order, so
 * callers pass boxes before keypoints. Previews and hidden shapes are skipped.
 */
export function pickEntityEditShape<T extends ShapeLike>(
  shapes: ReadonlyArray<T>,
  entityId: string,
  viewOrder: ReadonlyArray<string>,
  preferredView?: string,
): T | undefined {
  const rank = (shape: T) => {
    const view = shapeViewName(shape);
    if (preferredView !== undefined && view === preferredView) return -1;
    const index = view === undefined ? -1 : viewOrder.indexOf(view);
    return index < 0 ? viewOrder.length : index;
  };
  let best: T | undefined;
  for (const shape of shapes) {
    if (isPreviewShape(shape) || shape.ui?.displayControl.hidden) continue;
    if (shapeTopEntityId(shape) !== entityId) continue;
    if (best === undefined || rank(shape) < rank(best)) best = shape;
  }
  return best;
}

/** The distinct frames a track has a keyframe on, in order. */
export function trackKeyframeFrames(tracklet: TrackLike): number[] {
  const frames = new Set<number>();
  for (const child of tracklet.ui.childs ?? []) {
    if (typeof child.ui.frame_index === "number") frames.add(child.ui.frame_index);
  }
  return [...frames].sort((a, b) => a - b);
}

export type TrackFrameActions = {
  /** The frame lies in the track's range. */
  inTrack: boolean;
  /** The track has a keyframe on the frame. */
  isKeyframe: boolean;
  /** An interpolated frame strictly inside the track. */
  canAddKeyframe: boolean;
  /** A keyframe that can go without leaving fewer than two keyframes. */
  canRemoveKeyframe: boolean;
  /** Splitting right after the frame leaves a non-empty track on each side. */
  canSplit: boolean;
};

/** Which keyframe and split actions make sense for `tracklet` on `frame`. */
export function trackFrameActions(tracklet: TrackLike, frame: number): TrackFrameActions {
  const { start_frame: start, end_frame: end } = tracklet.data;
  const keyframes = trackKeyframeFrames(tracklet);
  const isKeyframe = keyframes.includes(frame);
  return {
    inTrack: start <= frame && frame <= end,
    isKeyframe,
    canAddKeyframe: start < frame && frame < end && !isKeyframe,
    canRemoveKeyframe: isKeyframe && keyframes.length > 2,
    canSplit: start <= frame && frame < end,
  };
}
