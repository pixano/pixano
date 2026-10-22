/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Retiming a keyframe: dragging its tick to another frame. The drag preview and the commit
 * plan with the same functions, so they always agree. A keyframe moves between its neighbours
 * in its camera; moving a track's first or last keyframe moves the track's start or end, never
 * far enough for two tracks of one camera to overlap.
 */

import { hasFrame, nextKeyframe, previousKeyframe } from "./laneQueries";

/** A track as the planner reads it: `keyframes` distinct and ascending, `start <= end`. */
export interface RetimeTrack {
  readonly id: string;
  readonly view: string;
  readonly start: number;
  readonly end: number;
  readonly keyframes: ArrayLike<number>;
}

/** The `frame_index` range of a camera's frames, already clamped to the clip. */
export interface FrameRange {
  readonly first: number;
  readonly last: number;
}

/** The frames a keyframe can move to, both included. */
export interface RetimeBounds {
  readonly min: number;
  readonly max: number;
}

/** Why a move is refused. */
export type RetimeRejection = "no-keyframe" | "same-frame" | "out-of-bounds";

/** A moved track's range after the move. */
export interface RetimeTrackPlan {
  readonly id: string;
  readonly start: number;
  readonly end: number;
  readonly rangeChanged: boolean;
}

/** A move: the new range of every moved track, or why it is refused. */
export type RetimePlan =
  { ok: true; target: number; tracks: RetimeTrackPlan[] } | { ok: false; reason: RetimeRejection };

/** A keyframe to move, and the tracks around it. */
export interface RetimeInput {
  frame: number;
  /**
   * The tracks whose keyframe on `frame` moves: one per camera of a merged row, or several
   * tracks of one camera (a box track and a keypoints track).
   */
  owners: readonly RetimeTrack[];
  /** Every own track of the entity, owners included. */
  siblings: readonly RetimeTrack[];
  frameRange: (view: string) => FrameRange | null;
}

/** What retiming reads from a tracklet: its stored frame range and timestamps. */
export interface TrackletTiming {
  readonly start_frame: number;
  readonly end_frame: number;
  readonly start_timestamp: number;
  readonly end_timestamp: number;
}

/** A tracklet's timestamps; both -1 when it has none. */
export interface TrackletTimestamps {
  start_timestamp: number;
  end_timestamp: number;
}

/** How far, in seconds, a stored timestamp may sit from its frame's time and still match it. */
const TIMESTAMP_TOLERANCE = 1e-6;

/** The owners with a keyframe on `frame`: the tracks the move changes. */
function movingOwners(owners: readonly RetimeTrack[], frame: number): RetimeTrack[] {
  return owners.filter((owner) => hasFrame(owner.keyframes, frame));
}

/** Where one moving track's keyframe can go; null when its camera has no frame range. */
function ownerBounds(owner: RetimeTrack, input: RetimeInput): RetimeBounds | null {
  const range = input.frameRange(owner.view);
  if (!range) return null;
  let min = range.first;
  let max = range.last;
  const others = input.siblings.filter(
    (sibling) => sibling.view === owner.view && sibling.id !== owner.id,
  );
  for (const track of [owner, ...others]) {
    const previous = previousKeyframe(track.keyframes, input.frame);
    const next = nextKeyframe(track.keyframes, input.frame);
    if (previous !== null) min = Math.max(min, previous + 1);
    if (next !== null) max = Math.min(max, next - 1);
  }
  // The owner's range may grow up to a track it does not overlap, never onto it.
  for (const other of others) {
    if (other.end < owner.start) min = Math.max(min, other.end + 1);
    else if (other.start > owner.end) max = Math.min(max, other.start - 1);
  }
  return { min, max };
}

/** The bounds every moving track allows; null when one has none or `frame` falls outside. */
function movingBounds(moving: readonly RetimeTrack[], input: RetimeInput): RetimeBounds | null {
  if (moving.length === 0) return null;
  let min = -Infinity;
  let max = Infinity;
  for (const owner of moving) {
    const bounds = ownerBounds(owner, input);
    if (!bounds) return null;
    min = Math.max(min, bounds.min);
    max = Math.min(max, bounds.max);
  }
  return min <= input.frame && input.frame <= max ? { min, max } : null;
}

/**
 * Where the keyframe on `input.frame` can move: in each owner's camera, strictly between the
 * camera's other keyframes and short of its tracks the owner does not overlap. Null without an
 * owner on the frame, without a frame range, or when the frame is outside its bounds.
 */
export function keyframeRetimeBounds(input: RetimeInput): RetimeBounds | null {
  return movingBounds(movingOwners(input.owners, input.frame), input);
}

/**
 * The new range of each owner with a keyframe on `input.frame` once it moves to `target`: a
 * keyframe on a range boundary drags it, any other one extends the range only when it leaves it.
 */
export function planKeyframeRetime(input: RetimeInput & { target: number }): RetimePlan {
  const { frame, target } = input;
  const moving = movingOwners(input.owners, frame);
  if (moving.length === 0) return { ok: false, reason: "no-keyframe" };
  if (target === frame) return { ok: false, reason: "same-frame" };
  const bounds = movingBounds(moving, input);
  if (!bounds || !Number.isInteger(target) || target < bounds.min || target > bounds.max) {
    return { ok: false, reason: "out-of-bounds" };
  }
  const tracks = moving.map((track) => {
    const start = frame === track.start ? target : Math.min(track.start, target);
    const end = frame === track.end ? target : Math.max(track.end, target);
    return { id: track.id, start, end, rangeChanged: start !== track.start || end !== track.end };
  });
  return { ok: true, target, tracks };
}

/** Whether a frame's time is known. */
function isTime(value: number | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Whether a frame's time matches a stored timestamp. */
function matchesTime(frameTime: number | undefined, stored: number): boolean {
  return isTime(frameTime) && Math.abs(frameTime - stored) <= TIMESTAMP_TOLERANCE;
}

/**
 * The timestamps of a tracklet retimed to [`start`, `end`], in its stored convention: frame
 * numbers (the app's) become the new frames, frame times (an import's seconds) the new frames'
 * times. Anything else, or a pair the tracklet schema would refuse, is left unchanged.
 */
export function retimedTrackletTimestamps(
  timing: TrackletTiming,
  start: number,
  end: number,
  frameTimestamp: (frame: number) => number | undefined,
): TrackletTimestamps {
  const unchanged = {
    start_timestamp: timing.start_timestamp,
    end_timestamp: timing.end_timestamp,
  };
  if (timing.start_timestamp === -1 && timing.end_timestamp === -1) return unchanged;
  let retimed: TrackletTimestamps | null = null;
  if (timing.start_timestamp === timing.start_frame && timing.end_timestamp === timing.end_frame) {
    retimed = { start_timestamp: start, end_timestamp: end };
  } else if (
    matchesTime(frameTimestamp(timing.start_frame), timing.start_timestamp) &&
    matchesTime(frameTimestamp(timing.end_frame), timing.end_timestamp)
  ) {
    const startTime = frameTimestamp(start);
    const endTime = frameTimestamp(end);
    if (isTime(startTime) && isTime(endTime)) {
      retimed = { start_timestamp: startTime, end_timestamp: endTime };
    }
  }
  // The schema wants both timestamps set (above -1) and in order.
  const valid =
    retimed !== null &&
    retimed.start_timestamp > -1 &&
    retimed.start_timestamp <= retimed.end_timestamp;
  return valid ? retimed : unchanged;
}
