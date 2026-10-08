/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  buildDetectionTimelineLanes,
  buildTrackingTimelineVisualState,
} from "$lib/trackingTimeline";

describe("trackingTimeline", () => {
  it("shows a VOS single-anchor row with anchor-specific guidance", () => {
    const visualState = buildTrackingTimelineVisualState({
      variant: "vos",
      segments: [[12, 12]],
      keyframes: [12],
      pendingMarkerIndex: null,
      pendingInterval: null,
    });

    expect(visualState.completedBars).toEqual([
      {
        startFrame: 12,
        endFrame: 12,
        label: "1 anchor — scrub forward and press T",
      },
    ]);
    expect(visualState.markers).toEqual([{ frameIndex: 12, kind: "keyframe" }]);
    expect(visualState.pendingBar).toBeNull();
  });

  it("shows animated pending VOS work with persistent anchor markers", () => {
    const visualState = buildTrackingTimelineVisualState({
      variant: "vos",
      segments: [[2, 2]],
      keyframes: [2],
      pendingMarkerIndex: 6,
      pendingInterval: [2, 6],
    });

    expect(visualState.completedBars[0]?.label).toBeNull();
    expect(visualState.pendingBar).toEqual({
      startFrame: 2,
      endFrame: 6,
      label: "Tracking...",
    });
    expect(visualState.markers).toEqual([
      { frameIndex: 2, kind: "keyframe" },
      { frameIndex: 6, kind: "pending" },
    ]);
  });

  it("labels multiple completed segments consistently across tracking workflows", () => {
    const visualState = buildTrackingTimelineVisualState({
      variant: "vos",
      segments: [
        [2, 4],
        [8, 9],
      ],
      keyframes: [2, 4, 8, 9],
      pendingMarkerIndex: null,
      pendingInterval: null,
    });

    expect(visualState.completedBars.map((bar) => bar.label)).toEqual(["Seg 1", "Seg 2"]);
  });

  it("keeps rectangle tracking copy unchanged for a single keyframe", () => {
    const visualState = buildTrackingTimelineVisualState({
      variant: "bbox",
      segments: [[5, 5]],
      keyframes: [5],
      pendingMarkerIndex: null,
      pendingInterval: null,
    });

    expect(visualState.completedBars[0]?.label).toBe(
      "1 keyframe — navigate to another frame and draw",
    );
  });
});

describe("buildDetectionTimelineLanes", () => {
  it("draws one lane per track with its runs, colour and review state", () => {
    const lanes = buildDetectionTimelineLanes(
      [
        {
          trackId: 1,
          className: "person",
          frames: [0, 1, 2, 10, 11].map((frameIndex) => ({ frameIndex })),
        },
        { trackId: 2, className: null, frames: [4].map((frameIndex) => ({ frameIndex })) },
        { trackId: 3, className: "car", frames: [5, 6].map((frameIndex) => ({ frameIndex })) },
      ],
      {
        discardedTrackIds: [2],
        selectedTrackId: 3,
        maxGapFrames: 3,
        colorOf: (trackId) => `color-${trackId}`,
      },
    );

    expect(lanes).toEqual([
      {
        trackId: 1,
        label: "person #1",
        color: "color-1",
        segments: [
          [0, 2],
          [10, 11],
        ],
        state: "kept",
      },
      { trackId: 2, label: "object #2", color: "color-2", segments: [[4, 4]], state: "discarded" },
      { trackId: 3, label: "car #3", color: "color-3", segments: [[5, 6]], state: "selected" },
    ]);
  });

  it("labels a detection run's pending bar", () => {
    const visual = buildTrackingTimelineVisualState({
      variant: "detection",
      segments: [],
      keyframes: [],
      pendingMarkerIndex: null,
      pendingInterval: [3, 9],
    });
    expect(visual.pendingBar).toEqual({
      startFrame: 3,
      endFrame: 9,
      label: "Detecting and tracking...",
    });
  });
});
