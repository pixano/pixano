/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Keyframe queries on sorted frame lists and lanes: binary searches, so they stay cheap on
 * every frame change and pointer move, whatever the number of keyframes.
 */

import type { LaneGeom, TrackGeom } from "./types";

/** The first index whose value is `>= value` (the length when none). */
export function lowerBound(sorted: ArrayLike<number>, value: number): number {
  let low = 0;
  let high = sorted.length;
  while (low < high) {
    const mid = (low + high) >>> 1;
    if (sorted[mid] < value) low = mid + 1;
    else high = mid;
  }
  return low;
}

/** The first index whose value is `> value` (the length when none). */
export function upperBound(sorted: ArrayLike<number>, value: number): number {
  let low = 0;
  let high = sorted.length;
  while (low < high) {
    const mid = (low + high) >>> 1;
    if (sorted[mid] <= value) low = mid + 1;
    else high = mid;
  }
  return low;
}

/** The index of `frame` in `frames`, or -1. */
export function keyframeIndexAt(frames: ArrayLike<number>, frame: number): number {
  const index = lowerBound(frames, frame);
  return index < frames.length && frames[index] === frame ? index : -1;
}

/** The last keyframe strictly before `frame`, or null. */
export function previousKeyframe(frames: ArrayLike<number>, frame: number): number | null {
  const index = lowerBound(frames, frame) - 1;
  return index >= 0 ? frames[index] : null;
}

/** The first keyframe strictly after `frame`, or null. */
export function nextKeyframe(frames: ArrayLike<number>, frame: number): number | null {
  const index = upperBound(frames, frame);
  return index < frames.length ? frames[index] : null;
}

/**
 * The index of the keyframe nearest to a fractional `frame`, if it lies within
 * `maxDistance` frames; -1 otherwise. A tie goes to the earlier keyframe.
 */
export function nearestKeyframeIndex(
  frames: ArrayLike<number>,
  frame: number,
  maxDistance: number,
): number {
  if (frames.length === 0 || !Number.isFinite(frame)) return -1;
  const after = lowerBound(frames, frame);
  const before = after - 1;
  let best = -1;
  if (before >= 0) best = before;
  if (after < frames.length && (best < 0 || frames[after] - frame < frame - frames[best])) {
    best = after;
  }
  return best >= 0 && Math.abs(frames[best] - frame) <= maxDistance ? best : -1;
}

/** Whether a sorted frame list holds `frame`. */
export function hasFrame(frames: ArrayLike<number>, frame: number): boolean {
  return keyframeIndexAt(frames, frame) >= 0;
}

/** The tracks of a lane with a keyframe on `frame`, in lane order. */
export function laneOwnersAt(lane: LaneGeom, frame: number): TrackGeom[] {
  return lane.tracks.filter((track) => hasFrame(track.frames, frame));
}

/** The tracks of a lane whose range covers `frame`, in lane order. */
export function tracksCoveringFrame(lane: LaneGeom, frame: number): TrackGeom[] {
  return lane.tracks.filter((track) => track.start <= frame && frame <= track.end);
}

/** The color a keyframe of a lane is drawn in: its first owner's, else the lane's first track's. */
export function keyframeColorAt(lane: LaneGeom, frame: number): string {
  const owner = lane.tracks.find((track) => hasFrame(track.frames, frame));
  return (owner ?? lane.tracks[0])?.color ?? "";
}
