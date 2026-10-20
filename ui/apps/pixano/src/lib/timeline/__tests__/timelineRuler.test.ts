/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { formatTimecode, frameTime } from "../timeFormat";
import {
  createTimelineGeometry,
  frameToX,
  frameWindowOf,
  horizontalRenderWindow,
  horizontalWindowIndex,
  laneWidthForZoom,
} from "../timelineGeometry";
import {
  buildRulerMarks,
  chooseRulerLevels,
  DEFAULT_RULER_LABEL_METRICS,
  majorStepLadder,
  NICE_DURATIONS_S,
  nominalFrameRate,
  RULER_LABEL_GAP_PX,
  RULER_LABEL_OFFSET_PX,
  RULER_MEDIUM_MIN_PX,
  RULER_MINOR_MIN_PX,
  rulerLabelWidth,
  rulerRectPath,
  timeDecimalsForStep,
  type RulerLabel,
  type RulerLevels,
  type RulerMarks,
} from "../timelineRuler";
import type { TimelineGeometry } from "../types";

const LADDER_30 = [
  1, 2, 5, 10, 15, 30, 60, 150, 300, 450, 900, 1800, 3600, 9000, 18000, 27000, 54000, 108000,
  216000, 540000, 1080000,
];

function levelsOf(geometry: TimelineGeometry, fps: number): RulerLevels {
  return chooseRulerLevels(geometry.pxPerFrame, fps, geometry.lastFrame);
}

/** The ruler of a whole lane, as the component builds it. */
function wholeRuler(fps: number, lastFrame: number, laneWidth: number) {
  const geometry = createTimelineGeometry(lastFrame, laneWidth);
  const levels = levelsOf(geometry, fps);
  const frameWindow = frameWindowOf(geometry, { x0: 0, x1: laneWidth });
  return { geometry, levels, marks: buildRulerMarks(geometry, fps, levels, frameWindow) };
}

function labelLines(marks: { labels: { time: string; frameText: string }[] }): string[] {
  return marks.labels.map(({ time, frameText }) => `${time} ${frameText}`);
}

describe("constants", () => {
  it("match the design", () => {
    expect(RULER_MINOR_MIN_PX).toBe(3);
    expect(RULER_MEDIUM_MIN_PX).toBe(12);
    expect(RULER_LABEL_OFFSET_PX).toBe(6);
    expect(RULER_LABEL_GAP_PX).toBe(8);
    expect(NICE_DURATIONS_S).toEqual([
      0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 18000, 36000,
    ]);
    expect(Object.isFrozen(NICE_DURATIONS_S)).toBe(true);
    expect(DEFAULT_RULER_LABEL_METRICS).toEqual({ timeCharWidth: 6.6, frameCharWidth: 6 });
  });
});

describe("nominalFrameRate", () => {
  it.each([
    [29.97, 30],
    [23.976, 24],
    [59.94, 60],
    [25, 25],
    [30, 30],
    [30.3, 30],
    [30.4, 30.4],
    [12.5, 12.5],
    [0.5, 0.5],
    [0, 1],
    [-30, 1],
    [Number.NaN, 1],
    [Number.POSITIVE_INFINITY, 1],
  ])("reads %d fps as %d", (fps, expected) => {
    expect(nominalFrameRate(fps)).toBe(expected);
  });
});

describe("majorStepLadder", () => {
  it("adds the nice durations to 1, 2, 5 and 10 frames", () => {
    expect(majorStepLadder(30)).toEqual(LADDER_30);
    expect(majorStepLadder(10)).toEqual([
      1, 2, 5, 10, 20, 50, 100, 150, 300, 600, 1200, 3000, 6000, 9000, 18000, 36000, 72000, 180000,
      360000,
    ]);
  });

  it("builds an NTSC rate's ladder from its nominal rate", () => {
    expect(majorStepLadder(29.97)).toEqual(LADDER_30);
    expect(majorStepLadder(23.976)).toEqual(majorStepLadder(24));
  });

  it("skips the durations that do not land on whole frames", () => {
    const ladder = majorStepLadder(25);
    expect(ladder).toEqual([
      1, 2, 5, 10, 25, 50, 125, 250, 375, 750, 1500, 3000, 7500, 15000, 22500, 45000, 90000, 180000,
      450000, 900000,
    ]);
    expect(ladder).not.toContain(12);
    expect(ladder).not.toContain(13);
  });

  it("keeps half a second at 24 and 30 fps", () => {
    expect(majorStepLadder(24).slice(0, 8)).toEqual([1, 2, 5, 10, 12, 24, 48, 120]);
    expect(majorStepLadder(30).slice(0, 7)).toEqual([1, 2, 5, 10, 15, 30, 60]);
  });

  it("uses 1 fps when the rate is not usable", () => {
    const oneFps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 18000, 36000];
    expect(majorStepLadder(0)).toEqual(oneFps);
    expect(majorStepLadder(Number.NaN)).toEqual(oneFps);
  });

  it("is ascending, unique and made of whole frames for any rate", () => {
    for (const fps of [
      0.5, 1, 2.5, 5, 8, 10, 12, 12.5, 15, 23.976, 24, 25, 29.97, 30, 50, 60, 240,
    ]) {
      const ladder = majorStepLadder(fps);
      expect(ladder.slice(0, 2)).toEqual([1, 2]);
      expect([5, 10].every((step) => ladder.includes(step))).toBe(true);
      for (let i = 1; i < ladder.length; i += 1) expect(ladder[i]).toBeGreaterThan(ladder[i - 1]);
      for (const step of ladder) expect(Number.isInteger(step)).toBe(true);
    }
  });
});

describe("timeDecimalsForStep", () => {
  it.each([
    [15, 30, 1],
    [30, 30, 0],
    [1, 30, 3],
    [1, 25, 2],
    [10, 25, 1],
    [5, 30, 3],
    [15, 29.97, 1],
    [12, 24, 1],
    [1, 4, 2],
    [1, 8, 3],
    [1, 3, 3],
    [1800, 30, 0],
    [3, 0, 0],
  ])("prints a %d-frame step at %d fps with %d decimals", (step, fps, expected) => {
    expect(timeDecimalsForStep(step, fps)).toBe(expected);
  });
});

describe("rulerLabelWidth", () => {
  it.each([
    [0, 199, 30, 33],
    [1, 199, 30, 46.2],
    [2, 199, 25, 52.8],
    [3, 199, 30, 59.4],
    [0, 0, 30, 33],
    [0, 17999, 30, 36],
    [0, 107999, 30, 42],
    [0, 108000, 30, 46.2],
    [1, 108000, 30, 59.4],
  ])("is wide enough for %d decimals up to frame %d at %d fps (%d px)", (d, last, fps, width) => {
    expect(rulerLabelWidth(d, last, fps)).toBeCloseTo(width, 9);
  });

  it("takes measured character widths", () => {
    expect(rulerLabelWidth(1, 199, 30, { timeCharWidth: 7, frameCharWidth: 7 })).toBe(49);
    expect(rulerLabelWidth(0, 199, 30, { timeCharWidth: 5, frameCharWidth: 8 })).toBe(32);
  });

  it("counts the hours of the clock the labels print, with all their digits", () => {
    // 107999 frames last 3599.97 s at 30 fps, but 3603.6 s at 29.97 fps ("1:00:03.6").
    expect(rulerLabelWidth(1, 107999, 30)).toBeCloseTo(46.2, 9);
    expect(rulerLabelWidth(1, 107999, 29.97)).toBeCloseTo(59.4, 9);
    expect(formatTimecode(frameTime(107985, 29.97), 1)).toHaveLength(9);
    expect(rulerLabelWidth(0, 107891, 29.97)).toBe(42);
    expect(rulerLabelWidth(0, 86399, 23.976)).toBeCloseTo(46.2, 9);
    // From ten hours on, "10:00:00" takes 8 characters.
    expect(rulerLabelWidth(0, 1079999, 30)).toBe(48);
    expect(rulerLabelWidth(0, 1080000, 30)).toBeCloseTo(52.8, 9);
    expect(rulerLabelWidth(1, 1080000, 30)).toBeCloseTo(66, 9);
  });
});

describe("chooseRulerLevels", () => {
  it.each([
    [30, 199, 1208, 5.95, 15, 5, 1, 1],
    [30, 199, 748, 3.638, 30, 5, 1, 0],
    [30, 199, 823, 4.015, 15, 5, 1, 1],
    [29.97, 199, 1208, 5.95, 15, 5, 1, 1],
    [25, 199, 748, 3.638, 25, 5, 1, 0],
    [24, 199, 748, 3.638, 24, 12, 1, 0],
    [10, 199, 748, 3.638, 20, 5, 1, 0],
    [30, 19, 748, 38.105, 2, 1, null, 3],
    [30, 19, 1496, 77.474, 1, null, null, 3],
    [30, 17999, 748, 0.0402, 1800, 300, 150, 0],
    [30, 17999, 403898, 22.439, 5, 1, null, 3],
    [30, 108000, 748, 0.0067, 9000, 1800, 450, 0],
    [30, 216000, 748, 0.00335, 18000, 3600, 900, 0],
  ])(
    "%d fps, last frame %d, lane %d (%d px per frame) → %d / %s / %s, %d decimals",
    (fps, lastFrame, laneWidth, pxPerFrame, major, medium, minor, decimals) => {
      const geometry = createTimelineGeometry(lastFrame, laneWidth);
      expect(geometry.pxPerFrame).toBeCloseTo(pxPerFrame, 2);
      expect(levelsOf(geometry, fps)).toEqual({ major, medium, minor, decimals });
    },
  );

  it("shows half-second majors from 110 % zoom at the default width", () => {
    const at = (zoom: number) => createTimelineGeometry(199, laneWidthForZoom(748, zoom));
    expect(levelsOf(at(100), 30).major).toBe(30);
    expect(createTimelineGeometry(199, 822).pxPerFrame * 15).toBeLessThan(60.2);
    expect(levelsOf(createTimelineGeometry(199, 822), 30).major).toBe(30);
    expect(levelsOf(at(110), 30).major).toBe(15);
  });

  it("widens the major step for wider measured labels", () => {
    const metrics = { timeCharWidth: 12, frameCharWidth: 10 };
    expect(chooseRulerLevels(1184 / 199, 30, 199, metrics).major).toBe(30);
  });

  it("doubles the last ladder step when no step fits", () => {
    // 10 million frames at 1 fps: a label takes 54 + 14 px, the 10 h step only 2.6 px.
    expect(chooseRulerLevels(724 / 10_000_000, 1, 10_000_000)).toEqual({
      major: 1152000,
      medium: null,
      minor: null,
      decimals: 0,
    });
    expect(chooseRulerLevels(724 / 50_000_000, 30, 50_000_000)).toEqual({
      major: 8640000,
      medium: 1080000,
      minor: 216000,
      decimals: 0,
    });
  });

  it("falls back to the coarsest step on a scale it cannot use", () => {
    for (const pxPerFrame of [0, -2, Number.NaN]) {
      expect(chooseRulerLevels(pxPerFrame, 30, 199)).toEqual({
        major: 1080000,
        medium: null,
        minor: null,
        decimals: 0,
      });
    }
    expect(chooseRulerLevels(Number.POSITIVE_INFINITY, 30, 199)).toEqual({
      major: 1,
      medium: null,
      minor: null,
      decimals: 3,
    });
  });

  it("picks the first fitting major and the smallest dividing steps, at any zoom", () => {
    const actual: RulerLevels[] = [];
    const expected: RulerLevels[] = [];
    for (const fps of [10, 24, 25, 29.97, 30, 60]) {
      const ladder = majorStepLadder(fps);
      const divisor = (step: number, p: number, minPx: number) =>
        ladder.find((d) => d < step && step % d === 0 && d * p >= minPx) ?? null;
      for (const lastFrame of [19, 199, 17999, 108000]) {
        const fits = (step: number, p: number) =>
          step * p >= rulerLabelWidth(timeDecimalsForStep(step, fps), lastFrame, fps) + 6 + 8;
        for (const zoom of [100, 110, 137, 250, 1000, 5000, 20000, 100000]) {
          const p = createTimelineGeometry(lastFrame, laneWidthForZoom(748, zoom)).pxPerFrame;
          const major = ladder.find((step) => fits(step, p));
          const medium = divisor(major, p, 12);
          const minor = divisor(medium ?? major, p, 3);
          actual.push(chooseRulerLevels(p, fps, lastFrame));
          expected.push({ major, medium, minor, decimals: timeDecimalsForStep(major, fps) });
        }
      }
    }
    expect(actual).toEqual(expected);
  });
});

describe("buildRulerMarks", () => {
  it("labels the half seconds of the mockup lane, but not #195 at its right edge", () => {
    const { geometry, marks } = wholeRuler(30, 199, 1208);
    const majors = Array.from({ length: 14 }, (_, i) => 15 * i);
    expect(marks.major).toEqual(majors.map((frame) => frameToX(geometry, frame)));
    expect(marks.labels.slice(0, 3)).toEqual([
      { frame: 0, x: 12, time: "00:00.0", frameText: "#0" },
      { frame: 15, x: frameToX(geometry, 15), time: "00:00.5", frameText: "#15" },
      { frame: 30, x: frameToX(geometry, 30), time: "00:01.0", frameText: "#30" },
    ]);
    expect(marks.labels.map((label) => label.frame)).toEqual(majors.slice(0, 13));
    expect(marks.major).toContain(frameToX(geometry, 195));
  });

  it("puts every frame on one level only", () => {
    const { geometry, marks } = wholeRuler(30, 199, 1208);
    expect(marks.medium).toHaveLength(26);
    expect(marks.minor).toHaveLength(160);
    expect(marks.medium.slice(0, 3)).toEqual([5, 10, 20].map((f) => frameToX(geometry, f)));
    expect(marks.minor.slice(0, 5)).toEqual([1, 2, 3, 4, 6].map((f) => frameToX(geometry, f)));
    const all = [...marks.major, ...marks.medium, ...marks.minor];
    expect(new Set(all).size).toBe(200);
  });

  it.each([
    [30, 199, 748, ["00:00 #0", "00:01 #30"], 7, 7],
    [25, 199, 748, ["00:00 #0", "00:01 #25"], 8, 8],
    [24, 199, 748, ["00:00 #0", "00:01 #24"], 9, 8],
    [10, 199, 748, ["00:00 #0", "00:02 #20"], 10, 10],
    [30, 19, 748, ["00:00.000 #0", "00:00.067 #2"], 10, 9],
    [30, 17999, 748, ["00:00 #0", "01:00 #1800"], 10, 10],
    [30, 108000, 748, ["00:00 #0", "05:00 #9000"], 13, 12],
  ])(
    "%d fps, last frame %d, lane %d: labels %j, %d majors, %d labels",
    (fps, lastFrame, laneWidth, firstLabels, majorCount, labelCount) => {
      const { marks } = wholeRuler(fps, lastFrame, laneWidth);
      expect(labelLines(marks).slice(0, 2)).toEqual(firstLabels);
      expect(marks.major).toHaveLength(majorCount);
      expect(marks.labels).toHaveLength(labelCount);
    },
  );

  it("drops the label of the last major at the right edge, keeping its line", () => {
    const at24 = wholeRuler(24, 199, 748).marks;
    expect(at24.labels.at(-1)?.frame).toBe(168);
    expect(at24.major.at(-1)).toBe(frameToX(createTimelineGeometry(199, 748), 192));
    expect(wholeRuler(30, 19, 748).marks.labels.at(-1)?.frame).toBe(16);
    expect(wholeRuler(30, 108000, 748).marks.labels.at(-1)?.frame).toBe(99000);
  });

  it("prints hours from one hour on", () => {
    const { marks } = wholeRuler(30, 216000, 748);
    expect(labelLines(marks)).toContain("1:00:00 #108000");
    expect(labelLines(marks)).toContain("50:00 #90000");
  });

  it("prints the true time of an NTSC frame", () => {
    const short = wholeRuler(29.97, 199, 1208);
    expect(short.levels.major).toBe(15);
    expect(labelLines(short.marks).slice(0, 3)).toEqual([
      "00:00.0 #0",
      "00:00.5 #15",
      "00:01.0 #30",
    ]);
    const geometry = createTimelineGeometry(1999, 12000);
    const levels = levelsOf(geometry, 29.97);
    const frameWindow = frameWindowOf(geometry, {
      x0: frameToX(geometry, 1490),
      x1: frameToX(geometry, 1510),
    });
    const marks = buildRulerMarks(geometry, 29.97, levels, frameWindow);
    expect(levels.major).toBe(15);
    expect(labelLines(marks)).toEqual(["00:50.1 #1500"]);
  });

  it("labels frame 0 only when the window holds it", () => {
    const geometry = createTimelineGeometry(199, 1208);
    const levels = levelsOf(geometry, 30);
    expect(buildRulerMarks(geometry, 30, levels, { first: 0, last: 20 }).labels[0].frame).toBe(0);
    expect(buildRulerMarks(geometry, 30, levels, { first: 1, last: 20 }).labels[0].frame).toBe(15);
  });

  it("keeps to the clip and to the window", () => {
    const geometry = createTimelineGeometry(199, 1208);
    const levels = levelsOf(geometry, 30);
    const frames = (xs: number[]) => xs.map((x) => Math.round((x - 12) / geometry.pxPerFrame));
    const start = buildRulerMarks(geometry, 30, levels, { first: -30, last: 10 });
    expect(frames(start.major)).toEqual([0]);
    expect(frames(start.medium)).toEqual([5, 10]);
    expect(frames(start.minor)).toEqual([1, 2, 3, 4, 6, 7, 8, 9]);
    const end = buildRulerMarks(geometry, 30, levels, { first: 190, last: 400 });
    expect(frames(end.major)).toEqual([195]);
    expect(frames(end.medium)).toEqual([190]);
    expect(frames(end.minor)).toEqual([191, 192, 193, 194, 196, 197, 198, 199]);
    expect(buildRulerMarks(geometry, 30, levels, { first: 50, last: 40 })).toEqual({
      minor: [],
      medium: [],
      major: [],
      labels: [],
    });
  });

  it("draws only the majors of levels without medium and minor", () => {
    const geometry = createTimelineGeometry(19, 1496);
    const marks = buildRulerMarks(geometry, 30, levelsOf(geometry, 30), { first: 0, last: 19 });
    expect(marks.major).toHaveLength(20);
    expect(marks.medium).toEqual([]);
    expect(marks.minor).toEqual([]);
  });

  it("yields only positions inside a window in the middle of a long clip", () => {
    const laneWidth = laneWidthForZoom(748, 100000);
    const geometry = createTimelineGeometry(108000, laneWidth);
    const levels = levelsOf(geometry, 30);
    const pxWindow = horizontalRenderWindow(horizontalWindowIndex(374_000, 748), 748, laneWidth);
    const frameWindow = frameWindowOf(geometry, pxWindow);
    const marks = buildRulerMarks(geometry, 30, levels, frameWindow);
    const [lo, hi] = [frameToX(geometry, frameWindow.first), frameToX(geometry, frameWindow.last)];
    const all = [...marks.major, ...marks.medium, ...marks.minor];
    expect(levels).toEqual({ major: 15, medium: 5, minor: 1, decimals: 1 });
    expect(all).toHaveLength(frameWindow.last - frameWindow.first + 1);
    expect(all.every((x) => x >= lo && x <= hi)).toBe(true);
    expect(
      marks.labels.every(({ frame }) => frame >= frameWindow.first && frame <= frameWindow.last),
    ).toBe(true);
    expect(marks.labels.length).toBeGreaterThan(0);
  });

  it("visits the window, never the whole clip", () => {
    const geometry = createTimelineGeometry(2_000_000_000, 748);
    const levels: RulerLevels = { major: 30, medium: 5, minor: 1, decimals: 0 };
    const marks = buildRulerMarks(geometry, 30, levels, { first: 1e9, last: 1e9 + 60 });
    expect(marks.labels.map((label) => label.frameText)).toEqual(["#1000000020", "#1000000050"]);
    expect(marks.medium).toHaveLength(11);
    expect(marks.minor).toHaveLength(48);
  });

  it("emits at most ceil(window / spacing) + 2 positions per level", () => {
    const failures: string[] = [];
    for (const zoom of [100, 250, 1000, 7000, 40000, 100000]) {
      const geometry = createTimelineGeometry(108000, laneWidthForZoom(748, zoom));
      const p = geometry.pxPerFrame;
      const levels = levelsOf(geometry, 30);
      for (const [first, last] of [
        [0, 108000],
        [0, 0],
        [17, 18],
        [53890, 54217],
        [1234, 9876],
        [99999, 108000],
      ]) {
        const marks = buildRulerMarks(geometry, 30, levels, { first, last });
        const windowPx = (last - first) * p;
        const levelCounts: [number | null, number][] = [
          [levels.major, marks.major.length],
          [levels.medium, marks.medium.length],
          [levels.minor, marks.minor.length],
        ];
        for (const [step, count] of levelCounts) {
          const bound = step === null ? 0 : Math.ceil(windowPx / (step * p)) + 2;
          if (count > bound)
            failures.push(`zoom ${zoom}, ${first}–${last}, step ${step}: ${count}`);
        }
      }
    }
    expect(failures).toEqual([]);
  });

  it("matches a frame-by-frame reading of the whole clip, for any window", () => {
    const failures: string[] = [];
    for (const fps of [10, 24, 29.97, 30]) {
      for (const lastFrame of [0, 1, 19, 199, 1999]) {
        for (const zoom of [100, 137, 1000, 5000]) {
          const geometry = createTimelineGeometry(lastFrame, laneWidthForZoom(748, zoom));
          const levels = levelsOf(geometry, fps);
          const { major, medium, minor, decimals } = levels;
          const reach = RULER_LABEL_OFFSET_PX + rulerLabelWidth(decimals, lastFrame, fps);
          const windows = [
            [-20, lastFrame + 20],
            [0, 0],
            [3, 3],
            [lastFrame - 17, lastFrame + 5],
            [7, Math.floor(lastFrame / 2) + 11],
          ];
          for (const [first, last] of windows) {
            const expected: RulerMarks = { minor: [], medium: [], major: [], labels: [] };
            for (let frame = Math.max(0, first); frame <= Math.min(last, lastFrame); frame += 1) {
              const x = frameToX(geometry, frame);
              if (frame % major === 0) {
                expected.major.push(x);
                if (x + reach > geometry.laneWidth - 4) continue;
                const time = formatTimecode(frameTime(frame, fps), decimals);
                expected.labels.push({ frame, x, time, frameText: `#${frame}` });
              } else if (medium !== null && frame % medium === 0) expected.medium.push(x);
              else if (minor !== null && frame % minor === 0) expected.minor.push(x);
            }
            const actual = buildRulerMarks(geometry, fps, levels, { first, last });
            if (JSON.stringify(actual) !== JSON.stringify(expected)) {
              failures.push(
                `${fps} fps, last frame ${lastFrame}, zoom ${zoom}, [${first}, ${last}]`,
              );
            }
          }
        }
      }
    }
    expect(failures).toEqual([]);
  });

  it("keeps every label clear of the next major line and of the lane's end", () => {
    // Each ladder step just as it starts to fit, so its labels are as tight as they get.
    const printedWidth = ({ time, frameText }: RulerLabel) =>
      Math.max(time.length * 6.6, frameText.length * 6);
    const failures: string[] = [];
    for (const fps of [23.976, 24, 25, 29.97, 30, 59.94, 60]) {
      for (const lastFrame of [199, 17999, 86399, 107999, 108000, 215999, 1080000]) {
        for (const step of majorStepLadder(fps)) {
          const room = rulerLabelWidth(timeDecimalsForStep(step, fps), lastFrame, fps) + 14;
          const geometry = createTimelineGeometry(
            lastFrame,
            24 + (room / step) * lastFrame * 1.001,
          );
          const levels = levelsOf(geometry, fps);
          for (const center of [0, Math.round(3600 * fps), lastFrame]) {
            const frameWindow = {
              first: center - 4 * levels.major,
              last: center + 4 * levels.major,
            };
            const marks = buildRulerMarks(geometry, fps, levels, frameWindow);
            for (const label of marks.labels) {
              const right = label.x + RULER_LABEL_OFFSET_PX + printedWidth(label);
              const limit = Math.min(
                geometry.laneWidth - 4,
                (marks.major.find((x) => x > label.x) ?? Infinity) - RULER_LABEL_GAP_PX,
              );
              if (right > limit + 1e-6) {
                failures.push(
                  `${fps} fps, last frame ${lastFrame}: "${label.time}" #${label.frame}`,
                );
              }
            }
          }
        }
      }
    }
    expect(failures).toEqual([]);
  });

  it("drops labels by the measured widths", () => {
    const geometry = createTimelineGeometry(199, 748);
    const levels = levelsOf(geometry, 30);
    const frameWindow = { first: 0, last: 199 };
    // x(180) = 666.9: 6 + 5 · 15 px reaches 747.9, past 748 − 4.
    const wider = { timeCharWidth: 15, frameCharWidth: 6 };
    expect(buildRulerMarks(geometry, 30, levels, frameWindow).labels.at(-1)?.frame).toBe(180);
    expect(buildRulerMarks(geometry, 30, levels, frameWindow, wider).labels.at(-1)?.frame).toBe(
      150,
    );
  });
});

describe("rulerRectPath", () => {
  it.each([
    [[], 0, 44, 1, ""],
    [[12], 0, 44, 1, "M12 0h1v44h-1z"],
    [[12, 30.5], 0, 44, 1, "M12 0h1v44h-1zM30 0h1v44h-1z"],
    [[12], 39, 43, 2, "M11.5 39h1v4h-1z"],
    [[12], 35, 43, 3, "M11.667 35h1v8h-1z"],
    [[12.25], 0, 44, 1.5, "M12 0h1v44h-1z"],
    [[12], 2.5, 10, 1, "M12 2.5h1v7.5h-1z"],
    [[0.4], 0, 44, 1, "M0 0h1v44h-1z"],
    [[Number.NaN, 12, Number.POSITIVE_INFINITY], 0, 44, 1, "M12 0h1v44h-1z"],
  ])("draws %j from y %d to %d at dpr %d as %j", (xs, y0, y1, dpr, expected) => {
    expect(rulerRectPath(xs, y0, y1, dpr)).toBe(expected);
  });

  it("draws one bar per mark", () => {
    const { marks } = wholeRuler(30, 199, 1208);
    expect(rulerRectPath(marks.minor, 39, 43, 2).match(/M/g)).toHaveLength(160);
  });
});
