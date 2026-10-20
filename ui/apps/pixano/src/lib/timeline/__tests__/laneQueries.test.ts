/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  hasFrame,
  keyframeColorAt,
  keyframeIndexAt,
  laneOwnersAt,
  lowerBound,
  nearestKeyframeIndex,
  nextKeyframe,
  previousKeyframe,
  tracksCoveringFrame,
  upperBound,
} from "../laneQueries";
import type { LaneGeom, TrackGeom } from "../types";

const frames = Int32Array.from([0, 12, 25]);

function track(
  id: string,
  start: number,
  end: number,
  keyframes: number[],
  color = "#f00",
): TrackGeom {
  return { id, view: "cam1", start, end, color, frames: Int32Array.from(keyframes) };
}

function lane(tracks: TrackGeom[]): LaneGeom {
  return {
    view: "cam1",
    tracks,
    spans: tracks.map(({ start, end, color }) => ({ start, end, color })),
    frames: Int32Array.from(
      [...new Set(tracks.flatMap((t) => [...t.frames]))].sort((a, b) => a - b),
    ),
    capFrames: new Int32Array(0),
  };
}

describe("lowerBound / upperBound", () => {
  it("find insertion points", () => {
    expect(lowerBound(frames, 12)).toBe(1);
    expect(upperBound(frames, 12)).toBe(2);
    expect(lowerBound(frames, -1)).toBe(0);
    expect(upperBound(frames, 99)).toBe(3);
    expect(lowerBound(new Int32Array(0), 5)).toBe(0);
  });
});

describe("keyframe queries", () => {
  it("finds an exact keyframe", () => {
    expect(keyframeIndexAt(frames, 12)).toBe(1);
    expect(keyframeIndexAt(frames, 13)).toBe(-1);
    expect(hasFrame(frames, 25)).toBe(true);
    expect(hasFrame(frames, 26)).toBe(false);
  });

  it("finds the previous keyframe, strictly before", () => {
    expect(previousKeyframe(frames, 12)).toBe(0);
    expect(previousKeyframe(frames, 13)).toBe(12);
    expect(previousKeyframe(frames, 0)).toBeNull();
    expect(previousKeyframe(frames, 100)).toBe(25);
    expect(previousKeyframe(new Int32Array(0), 3)).toBeNull();
  });

  it("finds the next keyframe, strictly after", () => {
    expect(nextKeyframe(frames, 12)).toBe(25);
    expect(nextKeyframe(frames, 11)).toBe(12);
    expect(nextKeyframe(frames, 25)).toBeNull();
    expect(nextKeyframe(frames, -1)).toBe(0);
  });

  it("finds the nearest keyframe within a distance, ties to the earlier one", () => {
    expect(nearestKeyframeIndex(frames, 11.4, 1)).toBe(1);
    expect(nearestKeyframeIndex(frames, 6, 5)).toBe(-1);
    expect(nearestKeyframeIndex(frames, 6, 6)).toBe(0);
    expect(nearestKeyframeIndex(frames, 30, 10)).toBe(2);
    expect(nearestKeyframeIndex(frames, -2, 2)).toBe(0);
    expect(nearestKeyframeIndex(new Int32Array(0), 1, 10)).toBe(-1);
    expect(nearestKeyframeIndex(frames, Number.NaN, 10)).toBe(-1);
  });
});

describe("lane owners", () => {
  const a = track("a", 0, 58, [0, 12, 58], "#a00");
  const b = track("b", 20, 140, [20, 58, 140], "#0b0");
  const l = lane([a, b]);

  it("lists the tracks with a keyframe on a frame", () => {
    expect(laneOwnersAt(l, 58).map((t) => t.id)).toEqual(["a", "b"]);
    expect(laneOwnersAt(l, 12).map((t) => t.id)).toEqual(["a"]);
    expect(laneOwnersAt(l, 13)).toEqual([]);
  });

  it("lists the tracks covering a frame", () => {
    expect(tracksCoveringFrame(l, 30).map((t) => t.id)).toEqual(["a", "b"]);
    expect(tracksCoveringFrame(l, 100).map((t) => t.id)).toEqual(["b"]);
    expect(tracksCoveringFrame(l, 150)).toEqual([]);
  });

  it("colors a keyframe like its first owner", () => {
    expect(keyframeColorAt(l, 140)).toBe("#0b0");
    expect(keyframeColorAt(l, 58)).toBe("#a00");
    expect(keyframeColorAt(l, 999)).toBe("#a00");
    expect(keyframeColorAt(lane([]), 1)).toBe("");
  });
});
