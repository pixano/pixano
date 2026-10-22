/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { laneOwnersAt } from "../laneQueries";
import {
  buildEntityTrackModel,
  buildTrackGeom,
  buildTrackModels,
  buildUnionLane,
  buildViewLane,
  distinctSortedFrames,
  EMPTY_LANE,
  sortViewNames,
} from "../trackModel";
import type { LaneGeom, TrackGeom, TrackInput } from "../types";

const ORDER = ["cam1", "cam2", "cam3"];

function tracklet(
  id: string,
  entityId: string | undefined,
  view: string,
  start: number,
  end: number,
  frames: (number | undefined)[],
): TrackInput {
  return {
    id,
    data: { entity_id: entityId, view_name: view, start_frame: start, end_frame: end },
    ui: { childs: frames.map((frame) => ({ ui: { frame_index: frame } })) },
  };
}

function geom(id: string, view: string, start: number, end: number, frames: number[]): TrackGeom {
  return { id, view, start, end, color: `#${id}`, frames: Int32Array.from(frames) };
}

const colorOf = (track: TrackInput) => `#${track.id}`;
const values = (frames: Int32Array) => Array.from(frames);
const ids = (tracks: readonly TrackGeom[]) => tracks.map((track) => track.id);
const ranges = (lane: LaneGeom) => lane.spans.map(({ start, end }) => [start, end]);

const person1 = () => [
  tracklet("t1", "p1", "cam1", 0, 58, [0, 12, 25, 41, 58]),
  tracklet("t2", "p1", "cam1", 81, 186, [81, 96, 110, 131, 150, 168, 186]),
  tracklet("t3", "p1", "cam2", 20, 140, [20, 55, 90, 140]),
  tracklet("t4", "p1", "cam3", 150, 199, [150, 175, 199]),
];
const person2 = () => [
  tracklet(
    "u1",
    "p2",
    "cam1",
    0,
    31,
    Array.from({ length: 32 }, (_, frame) => frame),
  ),
  tracklet("u2", "p2", "cam2", 10, 70, [10, 30, 50, 70]),
];
const object1 = () => [tracklet("o1", "o1", "cam1", 5, 40, [5, 20, 40])];
const record = () => [...person1(), ...person2(), ...object1()];

describe("sortViewNames", () => {
  it("sorts in natural order and drops duplicates", () => {
    expect(sortViewNames(["cam10", "cam2", "Cam1", "left"])).toEqual([
      "Cam1",
      "cam2",
      "cam10",
      "left",
    ]);
    expect(sortViewNames(["right", "left", "right"])).toEqual(["left", "right"]);
    expect(sortViewNames(new Set(["b", "a"]))).toEqual(["a", "b"]);
    expect(sortViewNames([])).toEqual([]);
  });

  it("orders names the collator ties the same way whatever the input order", () => {
    expect(sortViewNames(["cam1", "cam01"])).toEqual(["cam01", "cam1"]);
    expect(sortViewNames(["cam01", "cam1"])).toEqual(["cam01", "cam1"]);
  });

  it("leaves its input untouched", () => {
    const names = ["b", "a"];
    sortViewNames(names);
    expect(names).toEqual(["b", "a"]);
  });
});

describe("distinctSortedFrames", () => {
  const childs = (frames: (number | undefined)[]) =>
    frames.map((frame) => ({ ui: { frame_index: frame } }));

  it("keeps each frame once, ascending", () => {
    expect(values(distinctSortedFrames(childs([0, 0, 1, 1, 5])))).toEqual([0, 1, 5]);
    expect(values(distinctSortedFrames(childs([0, 4])))).toEqual([0, 4]);
    expect(values(distinctSortedFrames(childs([5, 0])))).toEqual([0, 5]);
    expect(values(distinctSortedFrames(childs([3, 1, 3, 2, 1])))).toEqual([1, 2, 3]);
    expect(distinctSortedFrames(childs([4]))).toBeInstanceOf(Int32Array);
  });

  it("ignores missing, negative, fractional and out-of-range frames", () => {
    expect(values(distinctSortedFrames(childs([undefined, -1, 3])))).toEqual([3]);
    expect(values(distinctSortedFrames(childs([2.5, 1, NaN, Infinity, 2 ** 31, 1])))).toEqual([1]);
    expect(values(distinctSortedFrames(childs([9, -4, 2.5, 4])))).toEqual([4, 9]);
  });

  it("skips unusable frames on the sorted pass and on the fallback alike", () => {
    // Usable values 0, 0, 3, 3, 7: non-decreasing, one pass.
    expect(values(distinctSortedFrames(childs([0, undefined, 0, 3, 2.5, 3, -1, 7])))).toEqual([
      0, 3, 7,
    ]);
    // 5 then 2: the fallback.
    expect(values(distinctSortedFrames(childs([5, undefined, 2, 5, -1, 2.5, 2])))).toEqual([2, 5]);
  });

  it("returns one shared empty array when there is no frame", () => {
    const empty = distinctSortedFrames(undefined);
    expect(empty).toBeInstanceOf(Int32Array);
    expect(empty).toHaveLength(0);
    expect(distinctSortedFrames([])).toBe(empty);
    expect(distinctSortedFrames(childs([undefined, -2]))).toBe(empty);
  });

  it("returns the same Int32Array for the same array, without reading it again", () => {
    let reads = 0;
    const list = [0, 4, 4, 9].map((frame) => ({
      get ui() {
        reads++;
        return { frame_index: frame };
      },
    }));
    const frames = distinctSortedFrames(list);
    expect(values(frames)).toEqual([0, 4, 9]);
    expect(reads).toBe(4);
    expect(distinctSortedFrames(list)).toBe(frames);
    expect(reads).toBe(4);
  });

  it("recomputes for a new array or a changed length", () => {
    const list = childs([0, 4]);
    const frames = distinctSortedFrames(list);
    const copy = distinctSortedFrames(childs([0, 4]));
    expect(copy).not.toBe(frames);
    expect(values(copy)).toEqual([0, 4]);

    list.push({ ui: { frame_index: 2 } });
    const grown = distinctSortedFrames(list);
    expect(grown).not.toBe(frames);
    expect(values(grown)).toEqual([0, 2, 4]);
    expect(distinctSortedFrames(list)).toBe(grown);
  });
});

describe("buildTrackGeom", () => {
  it("normalises the range and reads the keyframes", () => {
    const track = tracklet("t", "e", "cam1", 20, 5, [5, 12, 20]);
    const result = buildTrackGeom(track, "#abc");
    expect(result).toEqual({
      id: "t",
      view: "cam1",
      start: 5,
      end: 20,
      color: "#abc",
      frames: Int32Array.from([5, 12, 20]),
    });
    expect(result.frames).toBe(distinctSortedFrames(track.ui.childs));
  });

  it("has no keyframe without children", () => {
    const track: TrackInput = {
      id: "t",
      data: { view_name: "cam1", start_frame: 3, end_frame: 8 },
      ui: {},
    };
    expect(buildTrackGeom(track, "#abc").frames).toHaveLength(0);
  });
});

describe("EMPTY_LANE", () => {
  it("is a frozen lane without view, tracks or frames", () => {
    expect(Object.isFrozen(EMPTY_LANE)).toBe(true);
    expect(Object.isFrozen(EMPTY_LANE.tracks)).toBe(true);
    expect(Object.isFrozen(EMPTY_LANE.spans)).toBe(true);
    expect(EMPTY_LANE.view).toBeNull();
    expect(EMPTY_LANE.tracks).toEqual([]);
    expect(EMPTY_LANE.spans).toEqual([]);
    expect(EMPTY_LANE.frames).toHaveLength(0);
    expect(EMPTY_LANE.capFrames).toHaveLength(0);
  });
});

describe("buildViewLane", () => {
  it("orders the tracks by start, end and id, with one span each", () => {
    const tracks = [
      geom("c", "cam1", 10, 20, []),
      geom("b", "cam1", 0, 30, []),
      geom("a", "cam1", 0, 30, []),
      geom("d", "cam1", 0, 5, []),
    ];
    const lane = buildViewLane("cam1", tracks);
    expect(lane.view).toBe("cam1");
    expect(ids(lane.tracks)).toEqual(["d", "a", "b", "c"]);
    expect(lane.spans).toEqual([
      { start: 0, end: 5, color: "#d" },
      { start: 0, end: 30, color: "#a" },
      { start: 0, end: 30, color: "#b" },
      { start: 10, end: 20, color: "#c" },
    ]);
    expect(ids(tracks)).toEqual(["c", "b", "a", "d"]);
  });

  it("keeps a split at F/F+1 as two spans with four caps", () => {
    const lane = buildViewLane("cam1", [
      geom("b", "cam1", 11, 20, [11, 20]),
      geom("a", "cam1", 0, 10, [0, 5, 10]),
    ]);
    expect(lane.spans).toEqual([
      { start: 0, end: 10, color: "#a" },
      { start: 11, end: 20, color: "#b" },
    ]);
    expect(values(lane.frames)).toEqual([0, 5, 10, 11, 20]);
    expect(values(lane.capFrames)).toEqual([0, 10, 11, 20]);
  });

  it("caps a keyframe only on its own track's start or end", () => {
    // Frame 5 is a keyframe of a and the start of b, which has no keyframe there.
    const lane = buildViewLane("cam1", [
      geom("a", "cam1", 0, 10, [0, 5, 10]),
      geom("b", "cam1", 5, 20, [12, 20]),
    ]);
    expect(values(lane.frames)).toEqual([0, 5, 10, 12, 20]);
    expect(values(lane.capFrames)).toEqual([0, 10, 20]);
  });

  it("has no cap on a range end without a keyframe", () => {
    const lane = buildViewLane("cam1", [geom("a", "cam1", 0, 19, [0, 12])]);
    expect(values(lane.capFrames)).toEqual([0]);
  });

  it("caps a single-frame track once", () => {
    const lane = buildViewLane("cam1", [geom("a", "cam1", 7, 7, [7])]);
    expect(lane.spans).toEqual([{ start: 7, end: 7, color: "#a" }]);
    expect(values(lane.frames)).toEqual([7]);
    expect(values(lane.capFrames)).toEqual([7]);
  });

  it("merges the keyframes of overlapping tracks, sorted and distinct", () => {
    const lane = buildViewLane("cam1", [
      geom("a", "cam1", 0, 50, [0, 25, 50]),
      geom("b", "cam1", 10, 30, [10, 25, 30]),
    ]);
    expect(values(lane.frames)).toEqual([0, 10, 25, 30, 50]);
    expect(values(lane.capFrames)).toEqual([0, 10, 30, 50]);
    expect(ranges(lane)).toEqual([
      [0, 50],
      [10, 30],
    ]);
  });

  it("keeps keyframes outside the range, with caps on the range ends only", () => {
    const lane = buildViewLane("cam1", [geom("a", "cam1", 5, 10, [2, 5, 10, 14])]);
    expect(values(lane.frames)).toEqual([2, 5, 10, 14]);
    expect(values(lane.capFrames)).toEqual([5, 10]);
  });

  it("draws a line without ticks for a track without keyframes", () => {
    const lane = buildViewLane("cam1", [geom("a", "cam1", 3, 9, [])]);
    expect(lane.spans).toEqual([{ start: 3, end: 9, color: "#a" }]);
    expect(lane.frames).toHaveLength(0);
    expect(lane.capFrames).toHaveLength(0);
  });

  it("is empty without tracks", () => {
    expect(buildViewLane("cam2", [])).toEqual({
      view: "cam2",
      tracks: [],
      spans: [],
      frames: new Int32Array(0),
      capFrames: new Int32Array(0),
    });
  });
});

describe("buildUnionLane", () => {
  it("is EMPTY_LANE without tracks", () => {
    expect(buildUnionLane([])).toBe(EMPTY_LANE);
  });

  it("merges overlapping and adjacent ranges, each in its first range's color", () => {
    const tracks = [
      geom("x", "cam1", 30, 40, [30, 40]),
      geom("y", "cam2", 0, 10, [0, 10]),
      geom("z", "cam2", 11, 20, [11, 20]),
      geom("w", "cam3", 0, 5, [0, 5]),
    ];
    const lane = buildUnionLane(tracks);
    expect(lane.view).toBeNull();
    expect(ids(lane.tracks)).toEqual(["x", "y", "z", "w"]);
    expect(lane.tracks).not.toBe(tracks);
    expect(lane.spans).toEqual([
      { start: 0, end: 20, color: "#w" },
      { start: 30, end: 40, color: "#x" },
    ]);
    expect(values(lane.frames)).toEqual([0, 5, 10, 11, 20, 30, 40]);
    expect(values(lane.capFrames)).toEqual([0, 20, 30, 40]);
  });

  it("keeps ranges one frame apart separate", () => {
    const lane = buildUnionLane([
      geom("a", "cam1", 0, 10, [0, 10]),
      geom("b", "cam2", 12, 20, [12, 20]),
    ]);
    expect(ranges(lane)).toEqual([
      [0, 10],
      [12, 20],
    ]);
    expect(values(lane.capFrames)).toEqual([0, 10, 12, 20]);
  });

  it("gives a tie on the range to the track that comes first", () => {
    const a = geom("a", "cam1", 0, 10, []);
    const b = geom("b", "cam2", 0, 10, []);
    expect(buildUnionLane([a, b]).spans).toEqual([{ start: 0, end: 10, color: "#a" }]);
    expect(buildUnionLane([b, a]).spans).toEqual([{ start: 0, end: 10, color: "#b" }]);
  });

  it("caps only the keyframes on a merged line's ends", () => {
    const lane = buildUnionLane([
      geom("a", "cam1", 0, 10, [0, 10]),
      geom("b", "cam2", 5, 30, [5, 20]),
    ]);
    expect(lane.spans).toEqual([{ start: 0, end: 30, color: "#a" }]);
    expect(values(lane.frames)).toEqual([0, 5, 10, 20]);
    expect(values(lane.capFrames)).toEqual([0]);
  });

  it("caps neither a keyframe outside the lines nor a line end without a keyframe", () => {
    const lane = buildUnionLane([
      geom("a", "cam1", 5, 10, [2, 5, 10]),
      geom("b", "cam2", 30, 40, [35]),
    ]);
    expect(ranges(lane)).toEqual([
      [5, 10],
      [30, 40],
    ]);
    expect(values(lane.frames)).toEqual([2, 5, 10, 35]);
    expect(values(lane.capFrames)).toEqual([5, 10]);
  });

  it("caps a single-frame span once", () => {
    const lane = buildUnionLane([
      geom("a", "cam1", 7, 7, [7]),
      geom("b", "cam2", 20, 25, [20, 25]),
    ]);
    expect(ranges(lane)).toEqual([
      [7, 7],
      [20, 25],
    ]);
    expect(values(lane.capFrames)).toEqual([7, 20, 25]);
  });
});

describe("buildEntityTrackModel", () => {
  it("builds the mockup's person 1", () => {
    const model = buildEntityTrackModel("p1", person1(), ORDER, colorOf);
    expect(model.entityId).toBe("p1");
    expect(model.firstFrame).toBe(0);
    expect(model.union.view).toBeNull();
    expect(model.union.spans).toEqual([{ start: 0, end: 199, color: "#t1" }]);
    expect(values(model.union.frames)).toEqual([
      0, 12, 20, 25, 41, 55, 58, 81, 90, 96, 110, 131, 140, 150, 168, 175, 186, 199,
    ]);
    expect(values(model.union.capFrames)).toEqual([0, 199]);
    expect(ids(model.union.tracks)).toEqual(["t1", "t2", "t3", "t4"]);
    expect(ids(laneOwnersAt(model.union, 150))).toEqual(["t2", "t4"]);

    expect([...model.byView.keys()]).toEqual(["cam1", "cam2", "cam3"]);
    const cam1 = model.byView.get("cam1");
    expect(cam1.spans).toEqual([
      { start: 0, end: 58, color: "#t1" },
      { start: 81, end: 186, color: "#t2" },
    ]);
    expect(values(cam1.capFrames)).toEqual([0, 58, 81, 186]);
    expect(values(model.byView.get("cam2").capFrames)).toEqual([20, 140]);
    expect(values(model.byView.get("cam3").capFrames)).toEqual([150, 199]);
  });

  it("builds the mockup's person 2", () => {
    const model = buildEntityTrackModel("p2", person2(), ORDER, colorOf);
    expect(model.union.spans).toEqual([{ start: 0, end: 70, color: "#u1" }]);
    expect(model.union.frames).toHaveLength(34);
    expect(values(model.union.capFrames)).toEqual([0, 70]);
  });

  it("uses the camera's lane as the union when one camera sees the entity", () => {
    const model = buildEntityTrackModel("o1", object1(), ORDER, colorOf);
    expect(model.byView.size).toBe(1);
    expect(model.union).toBe(model.byView.get("cam1"));
    expect(model.firstFrame).toBe(5);
  });

  it("keeps a split within a camera and merges it across cameras", () => {
    const split = [
      tracklet("a", "e", "cam1", 0, 10, [0, 5, 10]),
      tracklet("b", "e", "cam1", 11, 20, [11, 20]),
    ];
    const single = buildEntityTrackModel("e", split, ORDER, colorOf);
    expect(ranges(single.union)).toEqual([
      [0, 10],
      [11, 20],
    ]);
    expect(values(single.union.capFrames)).toEqual([0, 10, 11, 20]);

    const withCam2 = [...split, tracklet("c", "e", "cam2", 30, 40, [30, 40])];
    const multi = buildEntityTrackModel("e", withCam2, ORDER, colorOf);
    expect(ranges(multi.union)).toEqual([
      [0, 20],
      [30, 40],
    ]);
    expect(values(multi.union.capFrames)).toEqual([0, 20, 30, 40]);
    expect(values(multi.byView.get("cam1").capFrames)).toEqual([0, 10, 11, 20]);
  });

  it("ranks the views of viewOrder first, then the others in natural order", () => {
    const tracks = [
      tracklet("l", "e", "left", 0, 1, [0]),
      tracklet("c10", "e", "cam10", 0, 1, [0]),
      tracklet("c1", "e", "cam1", 0, 1, [0]),
      tracklet("c9", "e", "cam9", 0, 1, [0]),
      tracklet("c2", "e", "cam2", 0, 1, [0]),
    ];
    const model = buildEntityTrackModel("e", tracks, ["cam2", "cam1"], colorOf);
    expect([...model.byView.keys()]).toEqual(["cam2", "cam1", "cam9", "cam10", "left"]);
    expect(ids(model.union.tracks)).toEqual(["c2", "c1", "c9", "c10", "l"]);
  });

  it("normalises an inverted range and starts at the smallest start", () => {
    const model = buildEntityTrackModel(
      "e",
      [tracklet("a", "e", "cam1", 50, 60, [50, 60]), tracklet("b", "e", "cam2", 40, 12, [12, 40])],
      ORDER,
      colorOf,
    );
    expect(model.firstFrame).toBe(12);
    expect(model.byView.get("cam2").spans).toEqual([{ start: 12, end: 40, color: "#b" }]);
    expect(values(model.byView.get("cam2").capFrames)).toEqual([12, 40]);
  });

  it("ignores unusable frames and draws a line for a track without children", () => {
    const model = buildEntityTrackModel(
      "e",
      [
        tracklet("a", "e", "cam1", 0, 10, [undefined, -1, 2.5, 0, 10]),
        {
          id: "b",
          data: { entity_id: "e", view_name: "cam1", start_frame: 20, end_frame: 30 },
          ui: {},
        },
      ],
      ORDER,
      colorOf,
    );
    expect(model.union.spans).toEqual([
      { start: 0, end: 10, color: "#a" },
      { start: 20, end: 30, color: "#b" },
    ]);
    expect(values(model.union.frames)).toEqual([0, 10]);
    expect(values(model.union.capFrames)).toEqual([0, 10]);
  });

  it("caps a single-frame track", () => {
    const model = buildEntityTrackModel(
      "e",
      [tracklet("a", "e", "cam1", 7, 7, [7])],
      ORDER,
      colorOf,
    );
    expect(model.union.spans).toEqual([{ start: 7, end: 7, color: "#a" }]);
    expect(values(model.union.capFrames)).toEqual([7]);
  });

  it("is empty without tracks", () => {
    const model = buildEntityTrackModel("e", [], ORDER, colorOf);
    expect(model.union).toBe(EMPTY_LANE);
    expect(model.byView.size).toBe(0);
    expect(model.firstFrame).toBe(Infinity);
  });
});

describe("buildTrackModels", () => {
  it("gives an entity its own tracks only, never a sub-entity's", () => {
    const tracklets = [
      tracklet("car-track", "car", "cam1", 0, 50, [0, 25, 50]),
      tracklet("wheel-track", "wheel", "cam1", 10, 20, [10, 20]),
    ];
    const { models } = buildTrackModels(tracklets, ORDER, colorOf, null);
    expect([...models.keys()]).toEqual(["car", "wheel"]);
    expect(ids(models.get("car").union.tracks)).toEqual(["car-track"]);
    expect(values(models.get("car").union.frames)).toEqual([0, 25, 50]);
    expect(ids(models.get("wheel").union.tracks)).toEqual(["wheel-track"]);
  });

  it("keys the models in order of first appearance and skips tracklets without an entity", () => {
    const cache = buildTrackModels(
      [
        tracklet("b1", "b", "cam1", 0, 1, [0]),
        tracklet("x", undefined, "cam1", 0, 1, [0]),
        tracklet("a1", "a", "cam1", 0, 1, [0]),
        tracklet("y", "", "cam1", 0, 1, [0]),
        tracklet("b2", "b", "cam2", 5, 6, [5]),
      ],
      ORDER,
      colorOf,
      null,
    );
    expect(cache.viewKey).toBe("cam1\u0001cam2\u0001cam3");
    expect([...cache.models.keys()]).toEqual(["b", "a"]);
    expect(ids(cache.models.get("b").union.tracks)).toEqual(["b1", "b2"]);
  });

  it("builds the models buildEntityTrackModel builds", () => {
    const { models } = buildTrackModels(record(), ORDER, colorOf, null);
    expect(models.get("p1")).toEqual(buildEntityTrackModel("p1", person1(), ORDER, colorOf));
    expect(models.get("p2")).toEqual(buildEntityTrackModel("p2", person2(), ORDER, colorOf));
  });

  it("returns the previous cache for the same tracklets", () => {
    const tracklets = record();
    const first = buildTrackModels(tracklets, ORDER, colorOf, null);
    expect(buildTrackModels(tracklets, ORDER, colorOf, first)).toBe(first);
  });

  it("returns the previous cache for rebuilt tracklets with the same values", () => {
    const first = buildTrackModels(record(), ORDER, colorOf, null);
    const rebuilt = record();
    expect(buildTrackModels(rebuilt, ORDER, colorOf, first)).toBe(first);
    expect(buildTrackModels(rebuilt, ORDER, colorOf, first)).toBe(first);
  });

  it("reads no child on a hit", () => {
    let reads = 0;
    const child = (frame: number) => ({
      get ui() {
        reads++;
        return { frame_index: frame };
      },
    });
    const tracklets: TrackInput[] = [
      {
        id: "t",
        data: { entity_id: "e", view_name: "cam1", start_frame: 0, end_frame: 9 },
        ui: { childs: [0, 5, 9].map(child) },
      },
    ];
    const first = buildTrackModels(tracklets, ORDER, colorOf, null);
    expect(reads).toBeGreaterThan(0);
    reads = 0;
    expect(buildTrackModels(tracklets, ORDER, colorOf, first)).toBe(first);
    expect(reads).toBe(0);
  });

  it("rebuilds only the entity whose keyframes changed", () => {
    const tracklets = record();
    const first = buildTrackModels(tracklets, ORDER, colorOf, null);
    const moved = tracklets.map((track) =>
      track.id === "t3" ? tracklet("t3", "p1", "cam2", 20, 140, [20, 56, 90, 140]) : track,
    );
    const next = buildTrackModels(moved, ORDER, colorOf, first);
    expect(next).not.toBe(first);
    expect(next.models.get("p1")).not.toBe(first.models.get("p1"));
    expect(values(next.models.get("p1").byView.get("cam2").frames)).toEqual([20, 56, 90, 140]);
    expect(next.models.get("p2")).toBe(first.models.get("p2"));
    expect(next.models.get("o1")).toBe(first.models.get("o1"));
    expect(buildTrackModels(moved, ORDER, colorOf, next)).toBe(next);
  });

  it.each([
    { change: "range", tracks: [tracklet("o1", "o1", "cam1", 5, 41, [5, 20, 40])] },
    { change: "view", tracks: [tracklet("o1", "o1", "cam2", 5, 40, [5, 20, 40])] },
    { change: "id", tracks: [tracklet("o9", "o1", "cam1", 5, 40, [5, 20, 40])] },
    {
      change: "track count",
      tracks: [
        tracklet("o1", "o1", "cam1", 5, 40, [5, 20, 40]),
        tracklet("o2", "o1", "cam1", 50, 60, [50, 60]),
      ],
    },
  ])("rebuilds the entity whose $change changed", ({ tracks }) => {
    const first = buildTrackModels(record(), ORDER, colorOf, null);
    const next = buildTrackModels([...person1(), ...person2(), ...tracks], ORDER, colorOf, first);
    expect(next.models.get("o1")).not.toBe(first.models.get("o1"));
    expect(next.models.get("p1")).toBe(first.models.get("p1"));
    expect(next.models.get("p2")).toBe(first.models.get("p2"));
  });

  it("rebuilds the entity whose children array grew in place", () => {
    const childs = [5, 20, 40].map((frame) => ({ ui: { frame_index: frame } }));
    const object: TrackInput = {
      id: "o1",
      data: { entity_id: "o1", view_name: "cam1", start_frame: 5, end_frame: 40 },
      ui: { childs },
    };
    const tracklets = [...person1(), object];
    const first = buildTrackModels(tracklets, ORDER, colorOf, null);

    childs.push({ ui: { frame_index: 30 } });
    const next = buildTrackModels(tracklets, ORDER, colorOf, first);
    expect(next).not.toBe(first);
    expect(values(next.models.get("o1").union.frames)).toEqual([5, 20, 30, 40]);
    expect(next.models.get("p1")).toBe(first.models.get("p1"));
  });

  it("moves a track to the entity it now belongs to, and drops an entity left without", () => {
    const tracklets = record();
    const first = buildTrackModels(tracklets, ORDER, colorOf, null);

    const moved = tracklets.map((track) =>
      track.id === "u2" ? tracklet("u2", "o1", "cam2", 10, 70, [10, 30, 50, 70]) : track,
    );
    const next = buildTrackModels(moved, ORDER, colorOf, first);
    expect(ids(next.models.get("p2").union.tracks)).toEqual(["u1"]);
    expect(ids(next.models.get("o1").union.tracks)).toEqual(["o1", "u2"]);
    expect(next.models.get("p1")).toBe(first.models.get("p1"));

    const emptied = tracklets.map((track) =>
      track.id === "o1" ? tracklet("o1", "p2", "cam1", 5, 40, [5, 20, 40]) : track,
    );
    const after = buildTrackModels(emptied, ORDER, colorOf, first);
    expect([...after.models.keys()]).toEqual(["p1", "p2"]);
    expect(ids(after.models.get("p2").union.tracks)).toEqual(["u1", "o1", "u2"]);
  });

  it("keeps the same empty cache while no tracklet has an entity", () => {
    const empty = buildTrackModels([], ORDER, colorOf, null);
    expect(empty.models.size).toBe(0);
    expect(buildTrackModels([], ORDER, colorOf, empty)).toBe(empty);
    const orphan = [tracklet("x", undefined, "cam1", 0, 1, [0])];
    expect(buildTrackModels(orphan, ORDER, colorOf, empty)).toBe(empty);
  });

  it("rebuilds an entity whose tracks come in another order", () => {
    const tracklets = record();
    const first = buildTrackModels(tracklets, ORDER, colorOf, null);
    const swapped = [tracklets[1], tracklets[0], ...tracklets.slice(2)];
    const next = buildTrackModels(swapped, ORDER, colorOf, first);
    expect(next.models.get("p1")).not.toBe(first.models.get("p1"));
    expect(next.models.get("p1")).toEqual(first.models.get("p1"));
    expect(next.models.get("p2")).toBe(first.models.get("p2"));
  });

  it("rebuilds the entity whose color changed", () => {
    const tracklets = record();
    const first = buildTrackModels(tracklets, ORDER, colorOf, null);
    const recolor = (track: TrackInput) => (track.id === "u2" ? "#other" : colorOf(track));
    const next = buildTrackModels(tracklets, ORDER, recolor, first);
    expect(next.models.get("p2")).not.toBe(first.models.get("p2"));
    expect(next.models.get("p2").byView.get("cam2").spans[0].color).toBe("#other");
    expect(next.models.get("p1")).toBe(first.models.get("p1"));
    expect(next.models.get("o1")).toBe(first.models.get("o1"));
  });

  it("rebuilds every model when the view order changes", () => {
    const tracklets = record();
    const first = buildTrackModels(tracklets, ORDER, colorOf, null);
    const next = buildTrackModels(tracklets, ["cam2", "cam1", "cam3"], colorOf, first);
    expect(next.viewKey).toBe("cam2\u0001cam1\u0001cam3");
    expect([...next.models.keys()]).toEqual(["p1", "p2", "o1"]);
    for (const [entityId, model] of next.models) {
      expect(model).not.toBe(first.models.get(entityId));
    }
    expect([...next.models.get("p1").byView.keys()]).toEqual(["cam2", "cam1", "cam3"]);
  });

  it("drops a removed entity and keeps the others", () => {
    const tracklets = record();
    const first = buildTrackModels(tracklets, ORDER, colorOf, null);
    const next = buildTrackModels(
      tracklets.filter((track) => track.data.entity_id !== "p2"),
      ORDER,
      colorOf,
      first,
    );
    expect(next).not.toBe(first);
    expect([...next.models.keys()]).toEqual(["p1", "o1"]);
    expect(next.models.get("p1")).toBe(first.models.get("p1"));
    expect(next.models.get("o1")).toBe(first.models.get("o1"));
    expect(first.models.size).toBe(3);
  });

  it("adds a new entity and keeps the others", () => {
    const tracklets = record();
    const first = buildTrackModels(tracklets, ORDER, colorOf, null);
    const next = buildTrackModels(
      [...tracklets, tracklet("n1", "n", "cam3", 0, 9, [0, 9])],
      ORDER,
      colorOf,
      first,
    );
    expect(next).not.toBe(first);
    expect([...next.models.keys()]).toEqual(["p1", "p2", "o1", "n"]);
    expect(next.models.get("p1")).toBe(first.models.get("p1"));
    expect(next.models.get("o1")).toBe(first.models.get("o1"));
  });
});
