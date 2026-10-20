/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { nanoid } from "nanoid";

import {
  collectFrameAnnotations,
  getBBoxInterpolationIdentity,
  getKeypointsInterpolationIdentity,
} from "$lib/stores/frameAnnotationSelectors";
import { trackKeyframeFrames } from "$lib/stores/trackEditing";
import { currentFrameIndex, lastFrameIndex } from "$lib/stores/videoStores.svelte";
import {
  annotations,
  editedTrackletId,
  entities,
  views as workspaceViews,
} from "$lib/stores/workspaceStores.svelte";
import {
  keyframeRetimeBounds,
  planKeyframeRetime,
  retimedTrackletTimestamps,
  type RetimeBounds,
  type RetimeInput,
  type RetimeRejection,
  type RetimeTrack,
} from "$lib/timeline/keyframeRetime";
import {
  Annotation,
  BaseSchema,
  BBox,
  Entity,
  entityHasTracklets,
  Keypoints,
  Tracklet,
  type PerFrameAnnotationData,
  type SequenceFrame,
  type View,
} from "$lib/types/dataset";
import type { KeypointAnnotation } from "$lib/types/shapeTypes";
import { ToolType } from "$lib/types/tools";
import type { MView as MediaViews } from "$lib/types/workspace";
import { mapBBoxForDisplay, mapKeypointsForDisplay } from "$lib/utils/annotationMapping";
import { applyPixanoSourceFields } from "$lib/utils/entityLookupUtils";
import { appendAnnotationsSorted } from "$lib/utils/entityOperations";
import { boxLinearInterpolation, keypointsLinearInterpolation } from "$lib/utils/interpolation";
import { saveTo } from "$lib/utils/saveItemUtils";
import { findSequenceFrameByIndex, sequenceFrameRange } from "$lib/utils/videoFrameIdentity";
import { splitTrackInTwo, updateView } from "$lib/utils/videoOperations";
import { sortByFrameIndex } from "$lib/utils/videoUtils";
import { commitNormalizedWorkspaceRuntime } from "$lib/utils/workspaceRuntimeMutations";

type MView = Record<string, View | View[]>;

/**
 * Add a keyframe at `frameIndex` (the current frame by default) within a tracklet.
 * Materialises the interpolated bbox/keypoints displayed on that frame, found among
 * `bboxes` and `keypoints`, into real annotations.
 *
 * Returns `true` if new annotations were added, `false` otherwise.
 */
export function addKeyItemToTracklet(
  tracklet: Tracklet,
  entity: Entity,
  views: MView,
  bboxes: BBox[],
  keypoints: KeypointAnnotation[],
  frameIndex: number = currentFrameIndex.value,
): boolean {
  let newItemBBox: BBox | undefined = undefined;
  let newItemKpt: Keypoints | undefined = undefined;

  // Find interpolated bbox for the current frame
  const interpolatedBox = bboxes.find(
    (box) =>
      box.ui.frame_index === frameIndex &&
      tracklet.ui.childs.some((ann) => ann.id === box.ui?.startRef?.id),
  );
  if (interpolatedBox) {
    // The ghost's id (`start::frame`) is display-only and its data.frame_index is still the
    // start keyframe's: the keyframe gets a fresh id and the frame it is created on.
    newItemBBox = BBox.cloneForFrame(interpolatedBox, {
      id: nanoid(10),
      frame_index: interpolatedBox.ui.frame_index,
    });
    newItemBBox.ui.displayControl = { ...newItemBBox.ui.displayControl, editing: false };
    newItemBBox.data.tracklet_id = tracklet.id;
    applyPixanoSourceFields(newItemBBox);
    // Coords are denormalized: normalize them
    const currentSf = (views[newItemBBox.data.view_name] as SequenceFrame[])[
      newItemBBox.ui.frame_index
    ];
    const [x, y, w, h] = newItemBBox.data.coords;
    newItemBBox.data.coords = [
      x / currentSf.data.width,
      y / currentSf.data.height,
      w / currentSf.data.width,
      h / currentSf.data.height,
    ];
    saveTo("add", newItemBBox);
  }

  // Find interpolated keypoints for the current frame
  const interpolatedKpt = keypoints.find(
    (kpt) =>
      kpt.ui?.frame_index === frameIndex &&
      tracklet.ui.childs.some((ann) => ann.id === kpt.ui?.startRef?.id),
  );
  if (interpolatedKpt && interpolatedKpt.ui?.startRef) {
    const keypointsRef = annotations.value.find(
      (ann) => ann.id === interpolatedKpt.ui?.startRef?.id && ann.is_type(BaseSchema.Keypoints),
    ) as Keypoints;
    if (keypointsRef) {
      const currentSf = (views[keypointsRef.data.view_name] as SequenceFrame[])[
        interpolatedKpt.ui.frame_index
      ];
      const coords: number[] = [];
      const states: string[] = [];
      for (let vi = 0; vi < interpolatedKpt.graph.vertices.length; vi++) {
        const vertex = interpolatedKpt.graph.vertices[vi];
        coords.push(vertex.x / currentSf.data.width);
        coords.push(vertex.y / currentSf.data.height);
        const meta = interpolatedKpt.vertexMetadata[vi];
        states.push(meta?.state ? meta.state : "visible");
      }
      newItemKpt = Keypoints.cloneForFrame(keypointsRef, {
        id: nanoid(10),
        coords,
        states,
        view_name: interpolatedKpt.viewRef.name,
        frame_id: interpolatedKpt.viewRef.id,
        frame_index: interpolatedKpt.ui.frame_index,
        displayControl: { ...interpolatedKpt.ui.displayControl, editing: false },
      });
      newItemKpt.data.tracklet_id = tracklet.id;
      applyPixanoSourceFields(newItemKpt);
      saveTo("add", newItemKpt);
    }
  }

  if (!newItemBBox && !newItemKpt) return false;
  const newTrackChildren: Annotation[] = [];
  if (newItemBBox) newTrackChildren.push(newItemBBox);
  if (newItemKpt) newTrackChildren.push(newItemKpt);
  commitNormalizedWorkspaceRuntime(
    appendAnnotationsSorted(annotations.value, newTrackChildren, sortByFrameIndex),
    entities.value,
  );
  return true;
}

/**
 * Binary search within a tracklet's children to find the frame indices of
 * the previous and next annotations relative to the current frame cursor.
 */
export function findPreviousAndNextFrames(
  tracklet: Tracklet,
  frameIndex: number = currentFrameIndex.value,
): [number, number] {
  let low = 0;
  let high = tracklet.ui.childs.length - 1;
  let mid = 0;
  let previousItem: Annotation | null = null;
  let nextItem: Annotation | null = null;

  while (low <= high) {
    mid = Math.floor((low + high) / 2);
    if (tracklet.ui.childs[mid].ui.frame_index <= frameIndex) {
      previousItem = tracklet.ui.childs[mid];
      low = mid + 1;
    } else {
      nextItem = tracklet.ui.childs[mid];
      high = mid - 1;
    }
  }
  return [
    previousItem ? previousItem.ui.frame_index : frameIndex,
    nextItem ? nextItem.ui.frame_index : frameIndex + 1,
  ];
}

/**
 * Glue `neighbor`, the closest track before or after `tracklet` (same object, same view),
 * onto `tracklet`: its keyframes move over, `tracklet` stretches across the gap, and
 * `neighbor` is deleted. The surviving range and every moved keyframe are saved (on load,
 * keyframes attach to the track their saved tracklet_id names), and edit mode on
 * `neighbor` carries over to `tracklet`.
 */
export function glueTracklets(tracklet: Tracklet, neighbor: Tracklet, entityId: string): void {
  const survivor =
    (annotations.value.find((ann) => ann.id === tracklet.id) as Tracklet | undefined) ?? tracklet;
  const moved = [...neighbor.ui.childs];
  for (const child of moved) child.data.tracklet_id = survivor.id;
  if (neighbor.data.end_frame < survivor.data.start_frame) {
    survivor.data.start_frame = neighbor.data.start_frame;
  } else {
    survivor.data.end_frame = neighbor.data.end_frame;
  }

  const nextEntities = entities.value.map((ent) => {
    if (ent.id === entityId) {
      ent.ui.childs = ent.ui.childs?.filter((ann) => ann.id !== neighbor.id);
    }
    return ent;
  });
  commitNormalizedWorkspaceRuntime(
    annotations.value.filter((ann) => ann.id !== neighbor.id),
    nextEntities,
  );

  applyPixanoSourceFields(survivor);
  saveTo("update", survivor);
  for (const child of moved) saveTo("update", child);
  saveTo("delete", neighbor);
  if (editedTrackletId.value === neighbor.id) editedTrackletId.value = survivor.id;
}

/** The boxes and keypoints `tracklet` interpolates on `frameIndex`, as displayed. */
export function interpolatedShapesAt(
  tracklet: Tracklet,
  frameIndex: number,
  views: MView,
): { bboxes: BBox[]; keypoints: KeypointAnnotation[] } {
  // The tracklet's views are media views (sequence frames), as the display mapping expects.
  const mediaViews = views as unknown as MediaViews;
  const common = {
    frameAnnotations: [],
    frameIdx: frameIndex,
    doInterpolate: true,
    tracks: [tracklet],
    mViews: mediaViews,
    focusedEntityId: null,
    selectedToolType: ToolType.Pan,
    entitiesById: null,
  };
  const { results: bboxes } = collectFrameAnnotations<BBox, BBox>({
    ...common,
    typeFilter: (ann): ann is BBox => ann.is_type(BaseSchema.BBox),
    mapForDisplay: (bbox, highlight) => mapBBoxForDisplay(bbox, mediaViews, highlight),
    interpolateFn: boxLinearInterpolation,
    interpolationIdentity: getBBoxInterpolationIdentity,
  });
  const { results: keypoints } = collectFrameAnnotations<Keypoints, KeypointAnnotation>({
    ...common,
    typeFilter: (ann): ann is Keypoints => ann.is_type(BaseSchema.Keypoints),
    mapForDisplay: (kpt, highlight) => mapKeypointsForDisplay(kpt, mediaViews, highlight),
    interpolateFn: keypointsLinearInterpolation,
    interpolationIdentity: getKeypointsInterpolationIdentity,
  });
  return { bboxes, keypoints };
}

/**
 * Split a tracklet right after `frameIndex`: the left part ends on that frame and the
 * right part starts on the next one. Interpolated boxes on these two frames become
 * keyframes first, so both parts keep showing what the track showed. When no box can be
 * materialised on one of them, the cut falls back to the nearest keyframes, so a part
 * never starts or ends without one.
 *
 * Returns `true` if the tracklet was split.
 */
export function splitTrackletAfter(
  tracklet: Tracklet,
  entity: Entity,
  frameIndex: number,
  views: MView,
): boolean {
  if (frameIndex < tracklet.data.start_frame || frameIndex >= tracklet.data.end_frame) {
    return false;
  }
  for (const frame of [frameIndex, frameIndex + 1]) {
    if (tracklet.ui.childs.some((ann) => ann.ui.frame_index === frame)) continue;
    const { bboxes, keypoints } = interpolatedShapesAt(tracklet, frame, views);
    addKeyItemToTracklet(tracklet, entity, views, bboxes, keypoints, frame);
  }
  const [prev, next] = findPreviousAndNextFrames(tracklet, frameIndex);
  const newOnRight = splitTrackInTwo(tracklet, prev, next);
  const nextEntities = entities.value.map((ent) => {
    if (entityHasTracklets(ent) && ent.id === entity.id) {
      ent.ui.childs = appendAnnotationsSorted(ent.ui.childs, [newOnRight], sortByFrameIndex);
    }
    return ent;
  });
  commitNormalizedWorkspaceRuntime(annotations.value.concat(newOnRight), nextEntities);
  return true;
}

/** A keyframe of an entity's timeline lane: its frame and the tracks with a keyframe on it. */
export interface KeyframeRef {
  entityId: string;
  frame: number;
  trackletIds: readonly string[];
}

export type KeyframeRetimeOutcome =
  | { ok: true; frame: number; movedIds: string[] }
  | { ok: false; reason: RetimeRejection | "no-frame" };

function ownTracklets(entityId: string): Tracklet[] {
  return annotations.value.filter(
    (annotation) =>
      annotation.is_type(BaseSchema.Tracklet) && annotation.data.entity_id === entityId,
  ) as Tracklet[];
}

function sequenceFramesOf(viewName: string): SequenceFrame[] | undefined {
  const view = workspaceViews.value[viewName];
  return Array.isArray(view) ? (view as SequenceFrame[]) : undefined;
}

function retimeTrackOf(tracklet: Tracklet): RetimeTrack {
  const { start_frame, end_frame, view_name } = tracklet.data;
  return {
    id: tracklet.id,
    view: view_name,
    start: Math.min(start_frame, end_frame),
    end: Math.max(start_frame, end_frame),
    keyframes: trackKeyframeFrames(tracklet),
  };
}

function retimeInputOf(ref: KeyframeRef, tracklets: Tracklet[]): RetimeInput {
  const siblings = tracklets.map(retimeTrackOf);
  const ownerIds = new Set(ref.trackletIds);
  return {
    frame: ref.frame,
    owners: siblings.filter((track) => ownerIds.has(track.id)),
    siblings,
    frameRange: (view) => sequenceFrameRange(sequenceFramesOf(view), lastFrameIndex.value),
  };
}

/** The frames a keyframe can be dragged to, for the drag preview; null when it cannot move. */
export function keyframeRetimeBoundsFor(ref: KeyframeRef): RetimeBounds | null {
  return keyframeRetimeBounds(retimeInputOf(ref, ownTracklets(ref.entityId)));
}

const seekFrame = (frame: number) => {
  currentFrameIndex.value = frame;
  updateView(frame);
};

/**
 * Move a keyframe of an entity to `target`: every annotation its tracks have on that frame
 * (box, keypoints, mask...) moves along, and a track's first or last keyframe drags the
 * track's start or end. The move is checked again here with the store's current data and is
 * all or nothing: it is refused when it would pass a neighbouring keyframe or track, or when
 * a camera has no frame `target`. The playhead then follows the keyframe.
 */
export function retimeKeyframe(
  ref: KeyframeRef & { target: number },
  { seek = seekFrame }: { seek?: (frame: number) => void } = {},
): KeyframeRetimeOutcome {
  const tracklets = ownTracklets(ref.entityId);
  const plan = planKeyframeRetime({ ...retimeInputOf(ref, tracklets), target: ref.target });
  if (plan.ok === false) return { ok: false, reason: plan.reason };

  const trackletsById = new Map(tracklets.map((tracklet) => [tracklet.id, tracklet]));
  const moves: { child: Annotation; frame: SequenceFrame }[] = [];
  for (const { id } of plan.tracks) {
    for (const child of trackletsById.get(id)?.ui.childs ?? []) {
      if (child.ui.frame_index !== ref.frame) continue;
      const frame = findSequenceFrameByIndex(sequenceFramesOf(child.data.view_name), ref.target);
      if (!frame) return { ok: false, reason: "no-frame" };
      moves.push({ child, frame });
    }
  }

  for (const { child, frame } of moves) {
    const data = child.data as PerFrameAnnotationData;
    // Annotations created in the app reference their frame as their view too.
    if (data.view_id === data.frame_id) data.view_id = frame.id;
    data.frame_id = frame.id;
    data.frame_index = ref.target;
    // The entity's state row of the old frame no longer describes it.
    data.entity_dynamic_state_id = "";
    child.ui.frame_index = ref.target;
    applyPixanoSourceFields(child);
  }
  for (const trackPlan of plan.tracks) {
    if (!trackPlan.rangeChanged) continue;
    const tracklet = trackletsById.get(trackPlan.id);
    if (!tracklet) continue;
    const frames = sequenceFramesOf(tracklet.data.view_name);
    const timestamps = retimedTrackletTimestamps(
      tracklet.data,
      trackPlan.start,
      trackPlan.end,
      (frame) => findSequenceFrameByIndex(frames, frame)?.data.timestamp,
    );
    tracklet.data.start_frame = trackPlan.start;
    tracklet.data.end_frame = trackPlan.end;
    tracklet.data.start_timestamp = timestamps.start_timestamp;
    tracklet.data.end_timestamp = timestamps.end_timestamp;
    applyPixanoSourceFields(tracklet);
    saveTo("update", tracklet);
  }

  commitNormalizedWorkspaceRuntime(annotations.value.slice(), entities.value);
  for (const { child } of moves) saveTo("update", child);
  seek(ref.target);
  return { ok: true, frame: ref.target, movedIds: moves.map(({ child }) => child.id) };
}
