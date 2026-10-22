/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { createTimelineGeometry, frameToX } from "../timelineGeometry";
import { hitTestLane, TICK_HIT_RADIUS_PX } from "../timelineHitTest";
import type { LaneGeom, TrackGeom } from "../types";

// lastFrame 100 on a 1024 px lane: innerWidth 1000, 10 px per frame, x = 12 + 10·f.
const g = createTimelineGeometry(100, 1024);
const x = (frame: number) => frameToX(g, frame);

function track(id: string, start: number, end: number, frames: number[], view = "cam1"): TrackGeom {
  return { id, view, start, end, color: "#f00", frames: Int32Array.from(frames) };
}

function lane(tracks: TrackGeom[], capFrames: number[] = []): LaneGeom {
  return {
    view: null,
    tracks,
    spans: tracks.map(({ start, end, color }) => ({ start, end, color })),
    frames: Int32Array.from(
      [...new Set(tracks.flatMap((t) => [...t.frames]))].sort((a, b) => a - b),
    ),
    capFrames: Int32Array.from(capFrames),
  };
}

// Keyframes 10 and 20 on a track over frames 0 to 30.
const a = track("a", 0, 30, [10, 20]);
const single = lane([a]);

describe("hitTestLane", () => {
  it("hits a tick within 4 px of a keyframe", () => {
    expect(TICK_HIT_RADIUS_PX).toBe(4);
    expect(hitTestLane(single, g, x(10) + 1)).toEqual({
      kind: "tick",
      frame: 10,
      isCap: false,
      owners: [a],
    });
    expect(hitTestLane(single, g, x(10) + 3.9)).toMatchObject({ kind: "tick", frame: 10 });
    expect(hitTestLane(single, g, x(20) - 3.9)).toMatchObject({ kind: "tick", frame: 20 });
  });

  it("hits a keyframe exactly 4 px away, on every frame and zoom", () => {
    // In frames, 4 px rounds: 10.4 - 10 > 4 / 10, and about half these pointers missed.
    for (let frame = 1; frame < 100; frame++) {
      const keyed = lane([track("k", 0, 100, [frame])]);
      expect(hitTestLane(keyed, g, x(frame) + 4)).toMatchObject({ kind: "tick", frame });
      expect(hitTestLane(keyed, g, x(frame) - 4)).toMatchObject({ kind: "tick", frame });
      expect(hitTestLane(keyed, g, x(frame) + 4.5)).toMatchObject({ kind: "track" });
    }
    const mockup = createTimelineGeometry(199, 748);
    for (const frame of [12, 50, 150, 198]) {
      const keyed = lane([track("k", 0, 199, [frame])]);
      const at = frameToX(mockup, frame);
      expect(hitTestLane(keyed, mockup, at + 4)).toMatchObject({ kind: "tick", frame });
      expect(hitTestLane(keyed, mockup, at - 4)).toMatchObject({ kind: "tick", frame });
    }
  });

  it("measures the radius in px whatever the zoom", () => {
    // 1 px per frame: 4 px is 4 frames.
    const g1 = createTimelineGeometry(100, 124);
    const keyed = lane([track("t", 0, 100, [50])]);
    expect(hitTestLane(keyed, g1, frameToX(g1, 54))).toMatchObject({ kind: "tick", frame: 50 });
    expect(hitTestLane(keyed, g1, frameToX(g1, 46))).toMatchObject({ kind: "tick", frame: 50 });
    expect(hitTestLane(keyed, g1, frameToX(g1, 55))).toEqual({
      kind: "track",
      frame: 55,
      tracks: keyed.tracks,
    });
  });

  it("hits the track under the pointer past the radius", () => {
    expect(hitTestLane(single, g, x(10) + 6)).toEqual({ kind: "track", frame: 11, tracks: [a] });
    expect(hitTestLane(single, g, x(10) + 4.1)).toEqual({ kind: "track", frame: 10, tracks: [a] });
  });

  it("hits a gap where no track covers the frame", () => {
    expect(hitTestLane(single, g, x(35))).toEqual({ kind: "gap", frame: 35 });
  });

  it("lists every owner of a shared keyframe, in lane order", () => {
    const b = track("b", 15, 60, [20, 40], "cam2");
    expect(hitTestLane(lane([a, b]), g, x(20))).toEqual({
      kind: "tick",
      frame: 20,
      isCap: false,
      owners: [a, b],
    });
    expect(hitTestLane(lane([b, a]), g, x(20))).toMatchObject({ owners: [b, a] });
    expect(hitTestLane(lane([a, b]), g, x(40))).toMatchObject({ frame: 40, owners: [b] });
  });

  it("lists the tracks covering a frame in lane order", () => {
    const c = track("c", 25, 60, [40]);
    expect(hitTestLane(lane([a, c]), g, x(28))).toEqual({
      kind: "track",
      frame: 28,
      tracks: [a, c],
    });
  });

  it("tells a cap from a tick", () => {
    const d = track("d", 0, 30, [0, 10, 20, 30]);
    const capped = lane([d], [0, 30]);
    expect(hitTestLane(capped, g, x(30) - 2)).toEqual({
      kind: "tick",
      frame: 30,
      isCap: true,
      owners: [d],
    });
    expect(hitTestLane(capped, g, x(10))).toMatchObject({ frame: 10, isCap: false });
    // The lane padding still reaches the cap on frame 0.
    expect(hitTestLane(capped, g, x(0) - 3)).toMatchObject({ kind: "tick", frame: 0, isCap: true });
  });

  it("takes the nearer of a cap and a tick one frame apart, a tie to the earlier", () => {
    // 4 px per frame: the cap on 10 and the tick on 11 are 4 px apart.
    const g4 = createTimelineGeometry(100, 424);
    const x4 = (frame: number) => frameToX(g4, frame);
    const capped = lane([track("t", 10, 30, [10, 11, 30])], [10, 30]);

    expect(hitTestLane(capped, g4, x4(10) + 1.5)).toMatchObject({ frame: 10, isCap: true });
    expect(hitTestLane(capped, g4, x4(11) - 1.5)).toMatchObject({ frame: 11, isCap: false });
    expect(hitTestLane(capped, g4, x4(10) + 2)).toMatchObject({ frame: 10, isCap: true });
  });

  it("hits a keyframe outside its track's range, with that track as owner", () => {
    const outside = track("o", 0, 30, [10, 40]);
    const keyed = lane([outside]);
    expect(hitTestLane(keyed, g, x(40) + 2)).toEqual({
      kind: "tick",
      frame: 40,
      isCap: false,
      owners: [outside],
    });
    expect(hitTestLane(keyed, g, x(40) + 6)).toEqual({ kind: "gap", frame: 41 });
  });

  it("hits only tracks and gaps on a lane without keyframes", () => {
    const bare = track("b", 20, 40, []);
    expect(hitTestLane(lane([bare]), g, x(20))).toEqual({
      kind: "track",
      frame: 20,
      tracks: [bare],
    });
    expect(hitTestLane(lane([bare]), g, x(19) - 1)).toEqual({ kind: "gap", frame: 19 });
  });

  it("acts on the nearest keyframe inside a merged band, a tie to the earlier one", () => {
    // 2 px per frame: keyframes 10, 11 and 12 merge into a band.
    const g2 = createTimelineGeometry(100, 224);
    const x2 = (frame: number) => frameToX(g2, frame);
    const comb = lane([track("e", 0, 30, [10, 11, 12])]);

    expect(hitTestLane(comb, g2, x2(11) + 0.4)).toMatchObject({ kind: "tick", frame: 11 });
    expect(hitTestLane(comb, g2, x2(10.5))).toMatchObject({ kind: "tick", frame: 10 });
    expect(hitTestLane(comb, g2, x2(11.5))).toMatchObject({ kind: "tick", frame: 11 });
    expect(hitTestLane(comb, g2, x2(12) + 3)).toMatchObject({ kind: "tick", frame: 12 });
    expect(hitTestLane(comb, g2, x2(12) + 5)).toMatchObject({ kind: "track", frame: 15 });
  });

  it("takes the hit radius from the options", () => {
    expect(hitTestLane(single, g, x(10) + 6, { radiusPx: 8 })).toMatchObject({
      kind: "tick",
      frame: 10,
    });
    expect(hitTestLane(single, g, x(10) + 0.5, { radiusPx: 0 })).toEqual({
      kind: "track",
      frame: 10,
      tracks: [a],
    });
    expect(hitTestLane(single, g, x(10), { radiusPx: 0 })).toMatchObject({ kind: "tick" });
  });

  it("never hits a tick on a lane that hides its ticks", () => {
    const capped = lane([track("d", 0, 30, [0, 10, 30])], [0, 30]);
    expect(hitTestLane(single, g, x(10), { showTicks: false })).toEqual({
      kind: "track",
      frame: 10,
      tracks: [a],
    });
    expect(hitTestLane(capped, g, x(30), { showTicks: false })).toMatchObject({
      kind: "track",
      frame: 30,
    });
    expect(hitTestLane(single, g, x(10), { showTicks: true })).toMatchObject({ kind: "tick" });
  });

  it("clamps the frame under the pointer to the clip", () => {
    expect(hitTestLane(single, g, -500)).toEqual({ kind: "track", frame: 0, tracks: [a] });
    expect(hitTestLane(single, g, 5000)).toEqual({ kind: "gap", frame: 100 });
  });

  it("finds a gap on an empty lane", () => {
    const empty = lane([]);
    expect(hitTestLane(empty, g, x(50))).toEqual({ kind: "gap", frame: 50 });
    expect(hitTestLane(empty, g, x(50) + 1)).toEqual({ kind: "gap", frame: 50 });
  });
});
