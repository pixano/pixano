/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { createTimelineGeometry, frameToX, frameWindowOf } from "../timelineGeometry";
import { buildLaneMarks, lanePathData, TICK_MERGE_PX, type MarkGroup } from "../trackMarks";
import {
  MARKS_ENTITY,
  type LaneGeom,
  type Span,
  type TimelineGeometry,
  type TrackGeom,
} from "../types";

const RED = "#e5484d";
const BLUE = "#3e63dd";

const PERSON_1 = [0, 12, 20, 25, 41, 55, 58, 81, 90, 96, 110, 131, 140, 150, 168, 175, 186, 199];

function range(from: number, to: number, step = 1): number[] {
  return Array.from({ length: Math.floor((to - from) / step) + 1 }, (_, i) => from + i * step);
}

function track(id: string, start: number, end: number, frames: number[], color = RED): TrackGeom {
  return { id, view: "cam1", start, end, color, frames: Int32Array.from(frames) };
}

/** A lane literal whose keyframes are its tracks' keyframes. */
function lane(tracks: TrackGeom[], spans: Span[], capFrames: number[]): LaneGeom {
  const frames = [...new Set(tracks.flatMap((t) => [...t.frames]))].sort((a, b) => a - b);
  return {
    view: null,
    tracks,
    spans,
    frames: Int32Array.from(frames),
    capFrames: Int32Array.from(capFrames),
  };
}

/** A lane of one track: one span, with caps at its ends unless given. */
function trackLane(start: number, end: number, frames: number[], caps = [start, end]): LaneGeom {
  return lane([track("t", start, end, frames)], [{ start, end, color: RED }], caps);
}

/** The marks of a whole lane. */
function fullMarks(l: LaneGeom, g: TimelineGeometry, showTicks = true, mergePx?: number) {
  const frameWindow = { first: 0, last: g.lastFrame };
  return buildLaneMarks(l, g, frameWindow, { x0: 0, x1: g.laneWidth }, { showTicks, mergePx });
}

const xs = (g: TimelineGeometry, frames: number[]) => frames.map((f) => frameToX(g, f));

describe("buildLaneMarks", () => {
  it("draws the mockup's person 1 lane as one line, two caps and 16 ticks", () => {
    const g = createTimelineGeometry(199, 748);
    const groups = fullMarks(trackLane(0, 199, PERSON_1), g);

    expect(groups).toHaveLength(1);
    const [marks] = groups;
    expect(marks.color).toBe(RED);
    expect(marks.lines).toEqual([12, frameToX(g, 199)]);
    expect(marks.lines[1]).toBeCloseTo(736, 9);
    expect(marks.caps).toEqual(xs(g, [0, 199]));
    expect(marks.ticks).toEqual(xs(g, PERSON_1.slice(1, -1)));
    expect(marks.ticks).toHaveLength(16);
    expect(marks.bands).toEqual([]);
  });

  it("keeps person 2's comb as ticks at 3.6 px per frame", () => {
    const g = createTimelineGeometry(199, 748);
    const [marks] = fullMarks(trackLane(0, 70, [...range(0, 31), 50, 70]), g);

    expect(g.pxPerFrame).toBeCloseTo(3.638, 3);
    expect(marks.bands).toEqual([]);
    expect(marks.ticks).toEqual(xs(g, [...range(1, 31), 50]));
    expect(marks.ticks).toHaveLength(32);
    expect(marks.lines).toEqual([12, frameToX(g, 70)]);
    expect(marks.lines[1]).toBeCloseTo(266.67, 2);
    expect(marks.caps).toEqual(xs(g, [0, 70]));
  });

  it("merges person 2's comb into a band at 1.9 px per frame", () => {
    const g = createTimelineGeometry(199, 400);
    const [marks] = fullMarks(trackLane(0, 70, [...range(0, 31), 50, 70]), g);

    expect(g.pxPerFrame).toBeCloseTo(1.889, 3);
    expect(marks.bands).toEqual(xs(g, [1, 31]));
    expect(marks.ticks).toEqual(xs(g, [1, 31, 50]));
    expect(marks.lines).toEqual([12, frameToX(g, 70)]);
    expect(marks.lines[1]).toBeCloseTo(144.26, 2);
  });

  it("merges keyframes closer than 3 px, not keyframes 3 px apart", () => {
    expect(TICK_MERGE_PX).toBe(3);
    const l = trackLane(0, 100, [0, 40, 41, 100]);

    const atThree = createTimelineGeometry(100, 324);
    expect(atThree.pxPerFrame).toBe(3);
    const [apart] = fullMarks(l, atThree);
    expect(apart.ticks).toEqual(xs(atThree, [40, 41]));
    expect(apart.bands).toEqual([]);

    const below = createTimelineGeometry(100, 323);
    expect(below.pxPerFrame).toBe(2.99);
    const [merged] = fullMarks(l, below);
    expect(merged.bands).toEqual(xs(below, [40, 41]));
    expect(merged.ticks).toEqual(xs(below, [40, 41]));
  });

  it("merges a dense comb into one band with a full tick at each end", () => {
    const g = createTimelineGeometry(4999, 748);
    const [marks] = fullMarks(trackLane(0, 4999, range(0, 4999)), g);

    expect(g.pxPerFrame).toBeCloseTo(0.1448, 4);
    expect(marks.bands).toEqual(xs(g, [1, 4998]));
    expect(marks.ticks).toEqual(xs(g, [1, 4998]));
    expect(marks.caps).toEqual(xs(g, [0, 4999]));
    expect(marks.lines).toEqual([12, frameToX(g, 4999)]);
  });

  it("breaks a run at a cap", () => {
    // 1 px per frame: every gap below is under 3 px.
    const g = createTimelineGeometry(100, 124);

    const [split] = fullMarks(trackLane(0, 4, [0, 1, 2, 3, 4], [0, 2, 4]), g);
    expect(split.ticks).toEqual(xs(g, [1, 3]));
    expect(split.bands).toEqual([]);

    const [after] = fullMarks(trackLane(0, 10, [0, 1, 2, 3, 10]), g);
    expect(after.bands).toEqual(xs(g, [1, 3]));
    expect(after.ticks).toEqual(xs(g, [1, 3]));
  });

  it("merges at the distance given by mergePx", () => {
    const g = createTimelineGeometry(199, 748);
    const l = trackLane(0, 199, PERSON_1);

    const [never] = fullMarks(l, g, true, 0);
    expect(never.bands).toEqual([]);
    expect(never.ticks).toHaveLength(16);

    // 20 px is 5.5 frames here: 20→25 and 55→58 merge, 90→96 does not.
    const [wide] = fullMarks(l, g, true, 20);
    expect(wide.bands).toEqual(xs(g, [20, 25, 55, 58]));
    expect(wide.ticks).toEqual(xs(g, PERSON_1.slice(1, -1)));
  });

  it("draws only the lines and caps without ticks", () => {
    const g = createTimelineGeometry(199, 748);
    const [marks] = fullMarks(trackLane(0, 199, PERSON_1), g, false);

    expect(marks).toEqual({
      color: RED,
      lines: [12, frameToX(g, 199)],
      bands: [],
      ticks: [],
      caps: xs(g, [0, 199]),
    });
  });

  it("draws no line for a zero-length span, only its cap", () => {
    const g = createTimelineGeometry(100, 1024);
    expect(fullMarks(trackLane(7, 7, [7], [7]), g)).toEqual([
      { color: RED, lines: [], bands: [], ticks: [], caps: [frameToX(g, 7)] },
    ]);
  });

  it("draws no tick or band without showTicks, even on a dense comb", () => {
    const g = createTimelineGeometry(4999, 748);
    expect(fullMarks(trackLane(0, 4999, range(0, 4999)), g, false)).toEqual([
      { color: RED, lines: [12, frameToX(g, 4999)], bands: [], ticks: [], caps: xs(g, [0, 4999]) },
    ]);
  });

  it("draws the keyframes outside a track's range as ticks past its line", () => {
    const g = createTimelineGeometry(100, 1024);
    const [marks] = fullMarks(trackLane(20, 40, [10, 20, 30, 40, 60]), g);
    expect(marks.lines).toEqual(xs(g, [20, 40]));
    expect(marks.caps).toEqual(xs(g, [20, 40]));
    expect(marks.ticks).toEqual(xs(g, [10, 30, 60]));
  });

  it("draws no line for a span that ends on the window's left edge, but its cap", () => {
    // 10 px per frame; the window starts on frame 20, the span's last frame.
    const g = createTimelineGeometry(100, 1024);
    const pxWindow = { x0: frameToX(g, 20), x1: frameToX(g, 60) };
    const frameWindow = frameWindowOf(g, pxWindow);
    expect(frameWindow).toEqual({ first: 19, last: 61 });

    const [marks] = buildLaneMarks(trackLane(0, 20, [0, 10, 20]), g, frameWindow, pxWindow, {
      showTicks: true,
    });
    expect(marks.lines).toEqual([]);
    expect(marks.caps).toEqual(xs(g, [20]));
    // Frame 10 is the keyframe of margin, drawn out of the window.
    expect(marks.ticks).toEqual(xs(g, [10]));
  });

  it("makes one group per color, a shared keyframe in its first owner's", () => {
    const g = createTimelineGeometry(100, 1024);
    const a = track("a", 0, 50, [0, 20, 40, 50], RED);
    const b = track("b", 10, 100, [10, 40, 100], BLUE);
    const spans = [
      { start: 0, end: 50, color: RED },
      { start: 10, end: 100, color: BLUE },
    ];
    const groups = fullMarks(lane([a, b], spans, [0, 10, 50, 100]), g);

    expect(groups).toEqual([
      {
        color: RED,
        lines: xs(g, [0, 50]),
        bands: [],
        ticks: xs(g, [20, 40]),
        caps: xs(g, [0, 50]),
      },
      { color: BLUE, lines: xs(g, [10, 100]), bands: [], ticks: [], caps: xs(g, [10, 100]) },
    ]);
  });

  it("orders the groups by first appearance, spans first, then keyframes", () => {
    const g = createTimelineGeometry(100, 1024);
    // Union lane: one red span, while the first keyframe (frame 0) is blue.
    const a = track("a", 10, 100, [10, 60, 100], RED);
    const b = track("b", 0, 40, [0, 20, 40], BLUE);
    const groups = fullMarks(lane([a, b], [{ start: 0, end: 100, color: RED }], [0, 100]), g);

    expect(groups.map((group) => group.color)).toEqual([RED, BLUE]);
    expect(groups[0]).toEqual({
      color: RED,
      lines: xs(g, [0, 100]),
      bands: [],
      ticks: xs(g, [10, 60]),
      caps: xs(g, [100]),
    });
    expect(groups[1]).toEqual({
      color: BLUE,
      lines: [],
      bands: [],
      ticks: xs(g, [20, 40]),
      caps: xs(g, [0]),
    });
  });

  it("colors a band by its first keyframe and each end tick by its own", () => {
    const g = createTimelineGeometry(100, 124);
    const a = track("a", 0, 100, [0, 10, 11, 100], RED);
    const b = track("b", 12, 12, [12], BLUE);
    const groups = fullMarks(lane([a, b], [{ start: 0, end: 100, color: RED }], [0, 100]), g);

    expect(groups).toEqual([
      {
        color: RED,
        lines: xs(g, [0, 100]),
        bands: xs(g, [10, 12]),
        ticks: xs(g, [10]),
        caps: xs(g, [0, 100]),
      },
      { color: BLUE, lines: [], bands: [], ticks: xs(g, [12]), caps: [] },
    ]);
  });

  it("keeps to the window: ticks in it plus one keyframe on each side, the line clipped", () => {
    const g = createTimelineGeometry(4999, 74800);
    const pxWindow = { x0: 30000, x1: 32244 };
    const frameWindow = frameWindowOf(g, pxWindow);
    expect(frameWindow).toEqual({ first: 2003, last: 2156 });

    const l = trackLane(0, 4990, range(0, 4990, 10));
    const [marks] = buildLaneMarks(l, g, frameWindow, pxWindow, { showTicks: true });

    expect(marks.lines).toEqual([30000, 32244]);
    expect(marks.ticks).toEqual(xs(g, range(2000, 2160, 10)));
    expect(marks.ticks).toHaveLength(17);
    expect(marks.caps).toEqual([]);
    expect(marks.bands).toEqual([]);
  });

  it("cuts a band at the window margin and keeps a run starting inside the window", () => {
    // 1 px per frame; window frames 500..600.
    const g = createTimelineGeometry(1000, 1024);
    const frameWindow = { first: 500, last: 600 };
    const pxWindow = { x0: 512, x1: 612 };

    // Every frame a keyframe: the band ends on the keyframes of margin, out of sight.
    const comb = trackLane(0, 1000, range(0, 1000));
    const [cut] = buildLaneMarks(comb, g, frameWindow, pxWindow, { showTicks: true });
    expect(cut.bands).toEqual(xs(g, [499, 601]));
    expect(cut.ticks).toEqual(xs(g, [499, 601]));
    expect(cut.lines).toEqual([512, 612]);
    expect(cut.caps).toEqual([]);

    // A comb starting at 550 starts its band there; 300 is the keyframe of margin.
    const late = trackLane(0, 1000, [0, 300, ...range(550, 1000)]);
    const [inside] = buildLaneMarks(late, g, frameWindow, pxWindow, { showTicks: true });
    expect(inside.bands).toEqual(xs(g, [550, 601]));
    expect(inside.ticks).toEqual(xs(g, [300, 550, 601]));
  });

  it("skips the spans and caps outside the frame window", () => {
    const g = createTimelineGeometry(100, 1024);
    const a = track("a", 0, 10, [0, 5, 10]);
    const b = track("b", 60, 80, [60, 70, 80]);
    const spans = [
      { start: 0, end: 10, color: RED },
      { start: 60, end: 80, color: RED },
    ];
    const l = lane([a, b], spans, [0, 10, 60, 80]);
    const [marks] = buildLaneMarks(
      l,
      g,
      { first: 50, last: 100 },
      { x0: 500, x1: 1024 },
      { showTicks: true },
    );

    expect(marks.lines).toEqual(xs(g, [60, 80]));
    expect(marks.caps).toEqual(xs(g, [60, 80]));
    // Frame 10 is the keyframe of margin on the left: walked, but a cap, so not drawn.
    expect(marks.ticks).toEqual(xs(g, [70]));
  });

  it("returns no group for an empty lane or a window past every mark", () => {
    const g = createTimelineGeometry(100, 1024);
    expect(fullMarks(lane([], [], []), g)).toEqual([]);
    const l = trackLane(0, 10, [0, 5, 10]);
    expect(
      buildLaneMarks(l, g, { first: 50, last: 100 }, { x0: 500, x1: 1024 }, { showTicks: true }),
    ).toEqual([]);
  });

  it("reads only the keyframes of the window, plus binary searches", () => {
    // 15 px per frame, 10,000 keyframes every 10 frames.
    const g = createTimelineGeometry(99_999, 1_500_009);
    expect(g.pxPerFrame).toBe(15);
    let reads = 0;
    const frames = new Proxy(Int32Array.from(range(0, 99_990, 10)), {
      get(target, key) {
        if (typeof key === "string" && /^\d+$/.test(key)) reads++;
        const value: unknown = Reflect.get(target, key);
        return value;
      },
    });
    const l: LaneGeom = { ...trackLane(0, 99_990, []), frames };
    const pxWindow = { x0: 750_000, x1: 752_244 };
    const [marks] = buildLaneMarks(l, g, frameWindowOf(g, pxWindow), pxWindow, {
      showTicks: true,
    });

    expect(marks.ticks).toEqual(xs(g, range(49_990, 50_160, 10)));
    expect(reads).toBeLessThan(100);
  });
});

describe("lanePathData", () => {
  // lastFrame 10 on a 124 px lane: innerWidth 100, 10 px per frame.
  const g = createTimelineGeometry(10, 124);
  const [group] = fullMarks(trackLane(0, 10, [0, 5, 10]), g);

  it("builds the line, tick and cap paths", () => {
    expect(lanePathData(group, MARKS_ENTITY, 1, 0)).toEqual({
      lines: "M12 17H112V19H12Z",
      bands: "",
      ticks: "M62 13V23",
      caps: "M12.5 10.5V25.5M112.5 10.5V25.5",
    });
  });

  it("places x relative to the SVG's left edge", () => {
    expect(lanePathData(group, MARKS_ENTITY, 1, 10)).toEqual({
      lines: "M2 17H102V19H2Z",
      bands: "",
      ticks: "M52 13V23",
      caps: "M2.5 10.5V25.5M102.5 10.5V25.5",
    });
  });

  it("draws bands as rectangles of the tick's height, one subpath per mark", () => {
    const marks: MarkGroup = {
      color: RED,
      lines: [12, 40, 60, 112],
      bands: [20, 30],
      ticks: [20, 30],
      caps: [],
    };
    expect(lanePathData(marks, MARKS_ENTITY, 1, 0)).toEqual({
      lines: "M12 17H40V19H12ZM60 17H112V19H60Z",
      bands: "M20 12H30V24H20Z",
      ticks: "M20 13V23M30 13V23",
      caps: "",
    });
  });

  it("snaps edges and centers to the device pixels", () => {
    const marks: MarkGroup = {
      color: RED,
      lines: [12.3, 111.8],
      bands: [],
      ticks: [62.3],
      caps: [12],
    };
    // At dpr 2 the 3 px cap at 12 spans 10.5..13.5, on the half-pixel grid.
    expect(lanePathData(marks, MARKS_ENTITY, 2, 0)).toEqual({
      lines: "M12.5 17H112V19H12.5Z",
      bands: "",
      ticks: "M62.5 13V23",
      caps: "M12 10.5V25.5",
    });
    expect(lanePathData(marks, MARKS_ENTITY, 1, 0)).toEqual({
      lines: "M12 17H112V19H12Z",
      bands: "",
      ticks: "M62 13V23",
      caps: "M12.5 10.5V25.5",
    });
  });

  it("snaps and offsets band edges like line edges", () => {
    const marks: MarkGroup = { color: RED, lines: [], bands: [40.2, 80.7], ticks: [], caps: [] };
    // 30.2 and 70.7 on the half-pixel grid of dpr 2.
    expect(lanePathData(marks, MARKS_ENTITY, 2, 10).bands).toBe("M30 12H70.5V24H30Z");
  });

  it("prints three decimals at most", () => {
    const marks: MarkGroup = { color: RED, lines: [], bands: [], ticks: [62.2], caps: [] };
    expect(lanePathData(marks, MARKS_ENTITY, 3, 0).ticks).toBe("M62.333 13V23");
  });

  it("counts a dpr that is not positive or not finite as 1", () => {
    const one = lanePathData(group, MARKS_ENTITY, 1, 0);
    expect(lanePathData(group, MARKS_ENTITY, 0, 0)).toEqual(one);
    expect(lanePathData(group, MARKS_ENTITY, Number.NaN, 0)).toEqual(one);
    expect(lanePathData(group, MARKS_ENTITY, Number.POSITIVE_INFINITY, 0)).toEqual(one);
  });

  it("gives empty paths for an empty group", () => {
    const empty: MarkGroup = { color: RED, lines: [], bands: [], ticks: [], caps: [] };
    expect(lanePathData(empty, MARKS_ENTITY, 1, 0)).toEqual({
      lines: "",
      bands: "",
      ticks: "",
      caps: "",
    });
  });
});
