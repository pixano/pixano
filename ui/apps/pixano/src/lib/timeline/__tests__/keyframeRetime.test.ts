/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  keyframeRetimeBounds,
  planKeyframeRetime,
  retimedTrackletTimestamps,
  type RetimeInput,
  type RetimePlan,
  type RetimeTrack,
  type RetimeTrackPlan,
  type TrackletTimestamps,
  type TrackletTiming,
} from "../keyframeRetime";

function track(
  id: string,
  start: number,
  end: number,
  keyframes: number[],
  view = "cam",
): RetimeTrack {
  return { id, view, start, end, keyframes: Int32Array.from(keyframes) };
}

/** Frame ranges by camera; a camera that is not listed has none. */
function frameRanges(byView: Record<string, [number, number]>): RetimeInput["frameRange"] {
  return (view) => {
    const range = byView[view];
    return range ? { first: range[0], last: range[1] } : null;
  };
}

const CAM_20 = frameRanges({ cam: [0, 20] });
const CAM_40 = frameRanges({ cam: [0, 40] });
const TWO_CAMS_40 = frameRanges({ cam1: [0, 40], cam2: [0, 40] });

const A = track("A", 0, 10, [0, 5, 10]);

/** The keyframe on `frame` of `owners`, among `siblings` (the owners alone by default). */
function keyframe(
  frame: number,
  owners: RetimeTrack[],
  siblings: RetimeTrack[] = owners,
  frameRange: RetimeInput["frameRange"] = CAM_20,
): RetimeInput {
  return { frame, owners, siblings, frameRange };
}

function retime(input: RetimeInput, target: number): RetimePlan {
  return planKeyframeRetime({ ...input, target });
}

function moved(id: string, start: number, end: number, rangeChanged: boolean): RetimeTrackPlan {
  return { id, start, end, rangeChanged };
}

const OUT_OF_BOUNDS: RetimePlan = { ok: false, reason: "out-of-bounds" };

describe("keyframeRetimeBounds", () => {
  it("keeps a keyframe strictly between its neighbours, within its camera's frames", () => {
    expect(keyframeRetimeBounds(keyframe(5, [A]))).toEqual({ min: 1, max: 9 });
    expect(keyframeRetimeBounds(keyframe(0, [A]))).toEqual({ min: 0, max: 4 });
    expect(keyframeRetimeBounds(keyframe(10, [A]))).toEqual({ min: 6, max: 20 });
  });

  it("counts keyframes on frame 0 and on the camera's last frame as neighbours", () => {
    const a2 = track("A2", 0, 10, [0, 1, 10]);
    expect(keyframeRetimeBounds(keyframe(1, [a2]))).toEqual({ min: 1, max: 9 });
    const late = track("L", 10, 20, [10, 19, 20]);
    expect(keyframeRetimeBounds(keyframe(19, [late]))).toEqual({ min: 11, max: 19 });
  });

  it("stays on a camera's frames when they start after frame 0", () => {
    const late = track("L", 2, 10, [2, 6, 10]);
    const from2 = frameRanges({ cam: [2, 38] });
    expect(keyframeRetimeBounds(keyframe(2, [late], [late], from2))).toEqual({ min: 2, max: 5 });
    expect(retime(keyframe(2, [late], [late], from2), 1)).toEqual(OUT_OF_BOUNDS);
  });

  it("is bounded by the keyframes and ranges of the camera's other tracks", () => {
    const b = track("B", 15, 20, [15, 20]);
    expect(keyframeRetimeBounds(keyframe(10, [A], [A, b]))).toEqual({ min: 6, max: 14 });
    expect(keyframeRetimeBounds(keyframe(15, [b], [A, b]))).toEqual({ min: 11, max: 19 });
    expect(keyframeRetimeBounds(keyframe(20, [b], [A, b]))).toEqual({ min: 16, max: 20 });
  });

  it("ignores the tracks of other cameras", () => {
    const overlapping = track("O", 0, 20, [3, 7], "cam2");
    const after = track("P", 12, 15, [12, 15], "cam2");
    const siblings = [A, overlapping, after];
    expect(keyframeRetimeBounds(keyframe(5, [A], siblings))).toEqual({ min: 1, max: 9 });
    expect(keyframeRetimeBounds(keyframe(10, [A], siblings))).toEqual({ min: 6, max: 20 });
  });

  it("stops short of a later track of the camera that the owner does not overlap", () => {
    const b = track("B", 12, 30, [20, 30]);
    expect(keyframeRetimeBounds(keyframe(10, [A], [A, b], CAM_40))).toEqual({ min: 6, max: 11 });
    expect(keyframeRetimeBounds(keyframe(5, [A], [A, b], CAM_40))).toEqual({ min: 1, max: 9 });
  });

  it("stops short of a track without keyframes", () => {
    const empty = track("E", 14, 16, []);
    expect(keyframeRetimeBounds(keyframe(10, [A], [A, empty], CAM_40))).toEqual({
      min: 6,
      max: 13,
    });
  });

  it("stops after the end of an earlier track wider than its keyframes", () => {
    const t = track("T", 10, 20, [10, 15, 20]);
    const z = track("Z", 0, 7, [0, 3]);
    expect(keyframeRetimeBounds(keyframe(10, [t], [z, t], CAM_40))).toEqual({ min: 8, max: 14 });
  });

  it("keeps a single-keyframe track between the tracks around it", () => {
    const single = track("S", 7, 7, [7]);
    const before = track("Z", 0, 3, [0, 3]);
    const after = track("B", 10, 12, [10, 12]);
    expect(keyframeRetimeBounds(keyframe(7, [single], [before, single, after], CAM_40))).toEqual({
      min: 4,
      max: 9,
    });
  });

  it("is bounded by an overlapping track through its keyframes only", () => {
    const c = track("C", 5, 20, [8, 20]);
    expect(keyframeRetimeBounds(keyframe(10, [A], [A, c], CAM_40))).toEqual({ min: 9, max: 19 });
  });

  it("intersects the bounds of owners in several cameras", () => {
    const h = track("H", 0, 40, [0, 20, 40], "cam1");
    const i = track("I", 10, 30, [10, 20, 30], "cam2");
    expect(keyframeRetimeBounds(keyframe(20, [h, i], [h, i], TWO_CAMS_40))).toEqual({
      min: 11,
      max: 29,
    });
    // The camera with fewer frames sets the end.
    const j = track("J", 0, 10, [0, 10], "cam1");
    const k = track("K", 0, 10, [0, 10], "cam2");
    const shortCam2 = frameRanges({ cam1: [0, 40], cam2: [0, 12] });
    expect(keyframeRetimeBounds(keyframe(10, [j, k], [j, k], shortCam2))).toEqual({
      min: 1,
      max: 12,
    });
  });

  it("intersects the bounds of owners in one camera, ignoring their shared keyframe", () => {
    const j = track("J", 0, 10, [0, 5, 10]);
    const k = track("K", 0, 10, [0, 5, 10]);
    expect(keyframeRetimeBounds(keyframe(5, [j, k]))).toEqual({ min: 1, max: 9 });
    const inner = track("N", 2, 8, [2, 5, 8]);
    expect(keyframeRetimeBounds(keyframe(5, [j, inner]))).toEqual({ min: 3, max: 7 });
  });

  it("counts only the owners with a keyframe on the frame", () => {
    const elsewhere = track("M", 0, 20, [2, 8], "cam2");
    expect(keyframeRetimeBounds(keyframe(5, [A, elsewhere]))).toEqual({ min: 1, max: 9 });
    expect(keyframeRetimeBounds(keyframe(3, [A]))).toBeNull();
    expect(keyframeRetimeBounds(keyframe(5, []))).toBeNull();
  });

  it("reads an owner's own keyframes when the siblings leave it out", () => {
    expect(keyframeRetimeBounds(keyframe(5, [A], []))).toEqual({ min: 1, max: 9 });
  });

  it("leaves no room when the frames on both sides are keyframes", () => {
    const comb = track("V", 0, 4, [0, 1, 2, 3, 4]);
    expect(keyframeRetimeBounds(keyframe(2, [comb]))).toEqual({ min: 2, max: 2 });
  });

  it("returns null when an owner's camera has no frame range", () => {
    expect(keyframeRetimeBounds(keyframe(5, [A], [A], () => null))).toBeNull();
    const other = track("O", 0, 20, [5], "cam2");
    expect(keyframeRetimeBounds(keyframe(5, [A, other]))).toBeNull();
  });

  it("returns null when the frame is outside its own bounds", () => {
    expect(keyframeRetimeBounds(keyframe(5, [A], [A], frameRanges({ cam: [0, 3] })))).toBeNull();
    const outside = track("T", 0, 10, [0, 5, 12]);
    const next = track("S", 11, 20, [15, 20]);
    expect(keyframeRetimeBounds(keyframe(12, [outside], [outside, next]))).toBeNull();
  });
});

describe("planKeyframeRetime", () => {
  it("moves a track's start with its first keyframe", () => {
    expect(retime(keyframe(0, [A]), 2)).toEqual({
      ok: true,
      target: 2,
      tracks: [moved("A", 2, 10, true)],
    });
  });

  it("moves a track's end with its last keyframe", () => {
    expect(retime(keyframe(10, [A]), 12)).toEqual({
      ok: true,
      target: 12,
      tracks: [moved("A", 0, 12, true)],
    });
    expect(retime(keyframe(10, [A]), 6)).toEqual({
      ok: true,
      target: 6,
      tracks: [moved("A", 0, 6, true)],
    });
  });

  it("keeps the range when a middle keyframe moves", () => {
    expect(retime(keyframe(5, [A]), 7)).toEqual({
      ok: true,
      target: 7,
      tracks: [moved("A", 0, 10, false)],
    });
  });

  it("moves a single-keyframe track whole", () => {
    const single = track("S", 7, 7, [7]);
    expect(retime(keyframe(7, [single]), 9)).toEqual({
      ok: true,
      target: 9,
      tracks: [moved("S", 9, 9, true)],
    });
    expect(retime(keyframe(7, [single]), 0)).toEqual({
      ok: true,
      target: 0,
      tracks: [moved("S", 0, 0, true)],
    });
  });

  it("extends a range wider than its keyframes only when the target leaves it", () => {
    const wide = track("W", 0, 12, [3, 7, 10]);
    expect(retime(keyframe(10, [wide]), 11)).toEqual({
      ok: true,
      target: 11,
      tracks: [moved("W", 0, 12, false)],
    });
    expect(retime(keyframe(10, [wide]), 15)).toEqual({
      ok: true,
      target: 15,
      tracks: [moved("W", 0, 15, true)],
    });
    expect(retime(keyframe(3, [wide]), 1)).toEqual({
      ok: true,
      target: 1,
      tracks: [moved("W", 0, 12, false)],
    });
    const late = track("W2", 2, 12, [3, 7, 10]);
    expect(retime(keyframe(3, [late]), 0)).toEqual({
      ok: true,
      target: 0,
      tracks: [moved("W2", 0, 12, true)],
    });
  });

  it("plans every owner with a keyframe on the frame, in input order", () => {
    const j = track("J", 0, 10, [0, 5, 10]);
    const k = track("K", 0, 10, [0, 5, 10]);
    expect(retime(keyframe(0, [k, j]), 3)).toEqual({
      ok: true,
      target: 3,
      tracks: [moved("K", 3, 10, true), moved("J", 3, 10, true)],
    });
    const p = track("P", 0, 20, [0, 10, 20], "cam1");
    const q = track("Q", 10, 30, [10, 30], "cam2");
    expect(retime(keyframe(10, [p, q], [p, q], TWO_CAMS_40), 12)).toEqual({
      ok: true,
      target: 12,
      tracks: [moved("P", 0, 20, false), moved("Q", 12, 30, true)],
    });
    const elsewhere = track("M", 0, 20, [2, 8], "cam2");
    expect(retime(keyframe(5, [A, elsewhere]), 6)).toEqual({
      ok: true,
      target: 6,
      tracks: [moved("A", 0, 10, false)],
    });
  });

  it("refuses a frame no owner has a keyframe on", () => {
    const noKeyframe: RetimePlan = { ok: false, reason: "no-keyframe" };
    expect(retime(keyframe(3, [A]), 4)).toEqual(noKeyframe);
    expect(retime(keyframe(5, [track("L", 0, 10, [0, 10])]), 6)).toEqual(noKeyframe);
    expect(retime(keyframe(5, []), 6)).toEqual(noKeyframe);
    expect(retime(keyframe(3, [A]), 3)).toEqual(noKeyframe);
  });

  it("refuses a move onto the same frame", () => {
    const sameFrame: RetimePlan = { ok: false, reason: "same-frame" };
    expect(retime(keyframe(5, [A]), 5)).toEqual(sameFrame);
    expect(
      retime(
        keyframe(5, [A], [A], () => null),
        5,
      ),
    ).toEqual(sameFrame);
  });

  it("refuses a target outside the bounds", () => {
    expect(retime(keyframe(5, [A]), 0)).toEqual(OUT_OF_BOUNDS);
    expect(retime(keyframe(5, [A]), 10)).toEqual(OUT_OF_BOUNDS);
    expect(retime(keyframe(0, [A]), -1)).toEqual(OUT_OF_BOUNDS);
    expect(retime(keyframe(10, [A]), 21)).toEqual(OUT_OF_BOUNDS);
    expect(retime(keyframe(1, [track("A2", 0, 10, [0, 1, 10])]), 0)).toEqual(OUT_OF_BOUNDS);
    expect(retime(keyframe(2, [track("V", 0, 4, [0, 1, 2, 3, 4])]), 3)).toEqual(OUT_OF_BOUNDS);
  });

  it("accepts exactly the targets within the bounds", () => {
    for (let target = -2; target <= 22; target++) {
      const plan = retime(keyframe(5, [A]), target);
      if (target === 5) expect(plan).toEqual({ ok: false, reason: "same-frame" });
      else expect(plan.ok).toBe(target >= 1 && target <= 9);
    }
  });

  it("refuses a move that would make two tracks of one camera overlap", () => {
    const b = track("B", 12, 30, [20, 30]);
    expect(retime(keyframe(10, [A], [A, b], CAM_40), 12)).toEqual(OUT_OF_BOUNDS);
    expect(retime(keyframe(10, [A], [A, b], CAM_40), 11)).toEqual({
      ok: true,
      target: 11,
      tracks: [moved("A", 0, 11, true)],
    });
  });

  it("refuses a target that is not a whole frame", () => {
    expect(retime(keyframe(5, [A]), 6.5)).toEqual(OUT_OF_BOUNDS);
    expect(retime(keyframe(5, [A]), Number.NaN)).toEqual(OUT_OF_BOUNDS);
  });

  it("refuses every move when an owner's camera has no frame range", () => {
    expect(
      retime(
        keyframe(5, [A], [A], () => null),
        6,
      ),
    ).toEqual(OUT_OF_BOUNDS);
  });

  it("refuses every move when the frame is outside its own bounds", () => {
    const outside = track("T", 0, 10, [0, 5, 12]);
    const next = track("S", 11, 20, [15, 20]);
    expect(retime(keyframe(12, [outside], [outside, next]), 9)).toEqual(OUT_OF_BOUNDS);
  });
});

describe("keyframe retime on generated entities", () => {
  /** A deterministic pseudo-random integer in [min, max], the same on every run. */
  function generator(seed: number): (min: number, max: number) => number {
    let state = seed;
    return (min, max) => {
      state = (state * 1103515245 + 12345) % 2147483648;
      return min + Math.floor((state / 2147483648) * (max - min + 1));
    };
  }

  /**
   * Two cameras of tracks laid out left to right, some doubled by an overlapping track (a
   * keypoints track on a box track), some wider than their keyframes, some without any.
   */
  function entity(next: (min: number, max: number) => number): RetimeTrack[] {
    const tracks: RetimeTrack[] = [];
    for (const view of ["cam1", "cam2"]) {
      let start = next(0, 3);
      for (let count = next(1, 4); count > 0 && start <= 36; count -= 1) {
        const end = Math.min(40, start + next(0, 10));
        const frames = new Set([start, end]);
        for (let extra = next(0, 3); extra > 0; extra -= 1) frames.add(next(start, end));
        if (next(0, 3) === 0) frames.delete(start);
        const sorted = [...frames].sort((a, b) => a - b);
        tracks.push(track(`${view}-${tracks.length}`, start, end, sorted, view));
        if (next(0, 2) === 0) {
          const innerStart = next(start, end);
          const innerEnd = Math.min(40, next(innerStart, end + 3));
          const inner = [...new Set([innerStart, innerEnd])];
          tracks.push(track(`${view}-${tracks.length}`, innerStart, innerEnd, inner, view));
        }
        start = end + next(1, 5);
      }
    }
    return tracks;
  }

  it("plans exactly the targets within the bounds, and every plan keeps the camera valid", () => {
    const next = generator(2026);
    const ranges = frameRanges({ cam1: [0, 40], cam2: [2, 38] });
    const failures: string[] = [];
    let planned = 0;
    for (let run = 0; run < 400; run += 1) {
      const siblings = entity(next);
      const picked = siblings[next(0, siblings.length - 1)];
      if (picked.keyframes.length === 0) continue;
      const frame = picked.keyframes[next(0, picked.keyframes.length - 1)];
      const oneView = next(0, 1) === 0;
      const owners = siblings.filter(
        (s) => Array.from(s.keyframes).includes(frame) && (!oneView || s.view === picked.view),
      );
      const input = keyframe(frame, owners, siblings, ranges);
      const bounds = keyframeRetimeBounds(input);
      for (let target = -2; target <= 42; target += 1) {
        const plan = retime(input, target);
        const allowed =
          bounds !== null && target !== frame && target >= bounds.min && target <= bounds.max;
        if (plan.ok !== allowed) failures.push(`run ${run}, ${frame} → ${target}: bounds disagree`);
        if (plan.ok === false) continue;
        planned += 1;
        for (const moved of plan.tracks) {
          const before = owners.find((owner) => owner.id === moved.id);
          const keyframes = Array.from(before.keyframes, (k) => (k === frame ? target : k));
          if (keyframes.some((k) => k < moved.start || k > moved.end)) {
            failures.push(`run ${run}, ${frame} → ${target}: ${moved.id} misses a keyframe`);
          }
          for (const other of siblings) {
            if (other.view !== before.view) continue;
            const overlapped = other.start <= before.end && before.start <= other.end;
            const overlaps = other.start <= moved.end && moved.start <= other.end;
            if (!owners.includes(other) && !overlapped && overlaps) {
              failures.push(`run ${run}, ${frame} → ${target}: ${moved.id} runs into ${other.id}`);
            }
            // No keyframe of the camera from the old frame to the new one, the new one included.
            for (const k of Array.from(other.keyframes)) {
              if (k !== frame && (k - frame) * (k - target) <= 0) {
                failures.push(`run ${run}, ${frame} → ${target}: passes keyframe ${k}`);
              }
            }
          }
        }
      }
    }
    expect(failures).toEqual([]);
    expect(planned).toBeGreaterThan(1000);
  });
});

describe("retimedTrackletTimestamps", () => {
  function timing(
    start_frame: number,
    end_frame: number,
    start_timestamp: number,
    end_timestamp: number,
  ): TrackletTiming {
    return { start_frame, end_frame, start_timestamp, end_timestamp };
  }

  const times = (start_timestamp: number, end_timestamp: number) => ({
    start_timestamp,
    end_timestamp,
  });
  const noTime = (): number | undefined => undefined;
  const at25fps = (frame: number) => frame / 25;
  const clipOf20 = (frame: number) => (frame <= 20 ? frame / 25 : undefined);

  it("keeps missing timestamps", () => {
    expect(retimedTrackletTimestamps(timing(0, 10, -1, -1), 2, 10, at25fps)).toEqual(times(-1, -1));
  });

  it("writes the new frames when the timestamps are frame numbers", () => {
    expect(retimedTrackletTimestamps(timing(0, 10, 0, 10), 2, 10, noTime)).toEqual(times(2, 10));
    expect(retimedTrackletTimestamps(timing(7, 7, 7, 7), 9, 9, noTime)).toEqual(times(9, 9));
  });

  it("writes the new frames' times when the timestamps are the frames' times", () => {
    expect(retimedTrackletTimestamps(timing(0, 10, 0, 0.4), 2, 10, at25fps)).toEqual(
      times(0.08, 0.4),
    );
    expect(retimedTrackletTimestamps(timing(0, 10, 0, 0.4), 0, 12, at25fps)).toEqual(
      times(0, 0.48),
    );
  });

  it("matches the frames' times within a microsecond", () => {
    expect(retimedTrackletTimestamps(timing(0, 10, 0, 0.4000005), 2, 10, at25fps)).toEqual(
      times(0.08, 0.4),
    );
    expect(retimedTrackletTimestamps(timing(0, 10, 0, 0.400002), 2, 10, at25fps)).toEqual(
      times(0, 0.400002),
    );
  });

  it("prefers frame numbers when both conventions match", () => {
    expect(retimedTrackletTimestamps(timing(0, 0, 0, 0), 5, 5, at25fps)).toEqual(times(5, 5));
  });

  it("keeps the timestamps when a new frame has no time", () => {
    expect(retimedTrackletTimestamps(timing(0, 10, 0, 0.4), 2, 30, clipOf20)).toEqual(
      times(0, 0.4),
    );
  });

  it("keeps the timestamps when an old frame has no time", () => {
    expect(retimedTrackletTimestamps(timing(0, 10, 0, 0.4), 2, 10, noTime)).toEqual(times(0, 0.4));
    const nullAtZero = (frame: number) => (frame === 0 ? null : frame / 25);
    expect(retimedTrackletTimestamps(timing(0, 10, 0, 0.4), 2, 10, nullAtZero)).toEqual(
      times(0, 0.4),
    );
  });

  it("keeps timestamps that follow neither convention", () => {
    expect(retimedTrackletTimestamps(timing(0, 10, 5, 7), 2, 10, at25fps)).toEqual(times(5, 7));
    expect(retimedTrackletTimestamps(timing(0, 10, 0, 7), 2, 10, at25fps)).toEqual(times(0, 7));
  });

  it("keeps the timestamps when the result would be inverted", () => {
    expect(retimedTrackletTimestamps(timing(0, 10, 0, 10), 10, 2, noTime)).toEqual(times(0, 10));
    const backwards = (frame: number) => (frame === 2 ? 1 : frame / 25);
    expect(retimedTrackletTimestamps(timing(0, 10, 0, 0.4), 2, 10, backwards)).toEqual(
      times(0, 0.4),
    );
  });

  it("keeps the timestamps when the result is not a valid tracklet pair", () => {
    const unsetAt2 = (frame: number) => (frame === 2 ? -1 : frame / 25);
    expect(retimedTrackletTimestamps(timing(0, 10, 0, 0.4), 2, 10, unsetAt2)).toEqual(
      times(0, 0.4),
    );
    const nanAt2 = (frame: number) => (frame === 2 ? Number.NaN : frame / 25);
    expect(retimedTrackletTimestamps(timing(0, 10, 0, 0.4), 2, 10, nanAt2)).toEqual(times(0, 0.4));
  });

  it("returns only pairs the tracklet schema accepts", () => {
    // tracklet.py: both -1, or both set (above -1) and in order.
    const accepted = ({ start_timestamp: start, end_timestamp: end }: TrackletTimestamps) =>
      (start === -1 && end === -1) || (start > -1 && end > -1 && start <= end);
    const at3 = (value: number) => (frame: number) => (frame === 3 ? value : frame / 25);
    const clocks = [noTime, at25fps, clipOf20, at3(-1), at3(Number.NaN), at3(0.5)];
    const stored = [
      timing(0, 10, -1, -1),
      timing(0, 10, 0, 10),
      timing(0, 10, 0, 0.4),
      timing(2, 8, 0.08, 0.32),
      timing(0, 10, 5, 7),
    ];
    const failures: string[] = [];
    for (const [clock, frameTimestamp] of clocks.entries()) {
      for (const tracklet of stored) {
        for (let start = 0; start <= 12; start += 1) {
          for (let end = 0; end <= 12; end += 1) {
            const result = retimedTrackletTimestamps(tracklet, start, end, frameTimestamp);
            if (!accepted(result)) failures.push(`clock ${clock}, [${start}, ${end}]`);
          }
        }
      }
    }
    expect(failures).toEqual([]);
  });

  it("returns the timestamps alone, in a new object", () => {
    const stored = timing(0, 10, 5, 7);
    const result = retimedTrackletTimestamps(stored, 2, 10, at25fps);
    expect(result).not.toBe(stored);
    expect(Object.keys(result).sort()).toEqual(["end_timestamp", "start_timestamp"]);
  });
});
