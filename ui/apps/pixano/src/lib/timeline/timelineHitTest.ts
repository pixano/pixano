/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * What a pointer at a lane x points at: the nearest keyframe within a few px (inside a merged
 * band too), else the tracks covering the frame under it, else a gap. Binary searches only.
 */

import { hasFrame, laneOwnersAt, nearestKeyframeIndex, tracksCoveringFrame } from "./laneQueries";
import { frameToX, xToFrame, xToFrameFloat } from "./timelineGeometry";
import type { LaneGeom, TimelineGeometry, TrackGeom } from "./types";

/** How far from a keyframe, in px, a pointer still hits its tick. */
export const TICK_HIT_RADIUS_PX = 4;

/** What a pointer hits on a lane; `frame` is the keyframe hit, or the frame under the pointer. */
export type LaneHit =
  | { kind: "tick"; frame: number; isCap: boolean; owners: readonly TrackGeom[] }
  | { kind: "track"; frame: number; tracks: readonly TrackGeom[] }
  | { kind: "gap"; frame: number };

/** Options of `hitTestLane`. */
export interface LaneHitOptions {
  /** How far from a keyframe, in px, a pointer hits its tick (default `TICK_HIT_RADIUS_PX`). */
  readonly radiusPx?: number;
  /** Whether the lane draws its ticks; without them nothing is a tick hit (default true). */
  readonly showTicks?: boolean;
}

/** What a pointer at `laneX` (lane px) hits on a lane. */
export function hitTestLane(
  lane: LaneGeom,
  geometry: TimelineGeometry,
  laneX: number,
  options: LaneHitOptions = {},
): LaneHit {
  if (options.showTicks ?? true) {
    const index = nearestKeyframeIndex(lane.frames, xToFrameFloat(geometry, laneX), Infinity);
    const radiusPx = options.radiusPx ?? TICK_HIT_RADIUS_PX;
    // The radius is compared in px: turned into frames it rounds, and a pointer exactly
    // radiusPx away would hit some keyframes and miss others.
    if (index >= 0 && Math.abs(frameToX(geometry, lane.frames[index]) - laneX) <= radiusPx) {
      const frame = lane.frames[index];
      return {
        kind: "tick",
        frame,
        isCap: hasFrame(lane.capFrames, frame),
        owners: laneOwnersAt(lane, frame),
      };
    }
  }
  const frame = xToFrame(geometry, laneX);
  const tracks = tracksCoveringFrame(lane, frame);
  return tracks.length > 0 ? { kind: "track", frame, tracks } : { kind: "gap", frame };
}
