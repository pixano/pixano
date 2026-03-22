import { describe, expect, it } from "vitest";

import { buildTrackingTimelineVisualState } from "$lib/trackingTimeline";

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
