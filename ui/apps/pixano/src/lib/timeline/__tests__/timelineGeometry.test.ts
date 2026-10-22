/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  anchoredScrollLeft,
  badgeWidthForFrame,
  createTimelineGeometry,
  frameToX,
  frameWindowOf,
  horizontalRenderWindow,
  horizontalWindowIndex,
  horizontalWindowStep,
  laneWidthForZoom,
  playheadBadgeLeft,
  revealScrollLeft,
  snapCenter,
  snapEdge,
  TIMELINE_HEADER_WIDTH,
  TIMELINE_LANE_PAD_X,
  xToFrame,
  xToFrameFloat,
  zoomAnchorFrame,
} from "../timelineGeometry";

/** The app's default lane: 200 frames on 748 px (724 px inside the padding). */
const g = createTimelineGeometry(199, 748);
/** The same clip at 1000 % zoom. */
const zoomed = createTimelineGeometry(199, 7480);
/** 2 px per frame, so frameToX(f) = 12 + 2f exactly. */
const even = createTimelineGeometry(100, 224);
/** 12 px per frame, so frameToX(f) = 12 + 12f exactly. */
const wide = createTimelineGeometry(100, 1224);

describe("constants", () => {
  it("match the layout", () => {
    expect(TIMELINE_HEADER_WIDTH).toBe(236);
    expect(TIMELINE_LANE_PAD_X).toBe(12);
  });
});

describe("laneWidthForZoom", () => {
  it.each([
    [748, 100, 748],
    [748, 250, 1870],
    [748, 110, 823],
    [748, 50, 748],
    [-10, 200, 0],
  ])("is %d px at %d %% → %d", (viewport, zoom, expected) => {
    expect(laneWidthForZoom(viewport, zoom)).toBe(expected);
  });
});

describe("createTimelineGeometry", () => {
  it("maps 200 frames on the default lane", () => {
    expect(g).toMatchObject({ lastFrame: 199, laneWidth: 748, padX: 12, innerWidth: 724 });
    expect(g.pxPerFrame).toBe(724 / 199);
    expect(g.pxPerFrame).toBeCloseTo(3.6381909, 6);
  });

  it.each([
    [undefined, 0],
    [Number.NaN, 0],
    [-5, 0],
    [12.7, 12],
  ])("reads a last frame of %s as %d", (lastFrame, expected) => {
    expect(createTimelineGeometry(lastFrame, 100).lastFrame).toBe(expected);
  });

  it("keeps a single frame across the whole inner width", () => {
    expect(createTimelineGeometry(0, 748).pxPerFrame).toBe(724);
  });

  it("keeps at least 1 px inside a lane narrower than its padding", () => {
    const narrow = createTimelineGeometry(199, 10);
    expect(narrow.innerWidth).toBe(1);
    expect(Number.isFinite(narrow.pxPerFrame)).toBe(true);
    expect(createTimelineGeometry(199, -20)).toMatchObject({ laneWidth: 0, innerWidth: 1 });
  });

  it("takes a custom padding", () => {
    expect(createTimelineGeometry(100, 300, 50)).toMatchObject({ padX: 50, innerWidth: 200 });
  });
});

describe("frameToX / xToFrame", () => {
  it("puts frame 0 and the last frame on the inner edges", () => {
    expect(frameToX(g, 0)).toBe(12);
    expect(frameToX(g, 199)).toBeCloseTo(736, 9);
    expect(frameToX(even, 49.5)).toBe(111);
  });

  it("round-trips every frame", () => {
    for (let frame = 0; frame <= 199; frame += 1) {
      expect(xToFrame(g, frameToX(g, frame))).toBe(frame);
      expect(xToFrameFloat(g, frameToX(g, frame))).toBeCloseTo(frame, 9);
    }
  });

  it("picks the nearest frame and clamps to the clip", () => {
    expect(xToFrame(even, 32.9)).toBe(10);
    expect(xToFrame(even, 33.1)).toBe(11);
    expect(xToFrame(g, -50)).toBe(0);
    expect(xToFrame(g, 10_000)).toBe(199);
    expect(xToFrame(g, Number.NaN)).toBe(0);
    expect(xToFrameFloat(even, 0)).toBe(-6);
  });

  it("maps every x to frame 0 on a single-frame clip", () => {
    const single = createTimelineGeometry(0, 748);
    for (const x of [-100, 0, 12, 400, 1e6]) expect(xToFrame(single, x)).toBe(0);
  });
});

describe("horizontal render window", () => {
  it("steps by half a viewport, at least 128 px", () => {
    expect(horizontalWindowStep(748)).toBe(374);
    expect(horizontalWindowStep(749)).toBe(375);
    expect(horizontalWindowStep(100)).toBe(128);
    expect(horizontalWindowStep(0)).toBe(128);
    expect(horizontalWindowStep(Number.NaN)).toBe(128);
  });

  it("indexes a scroll position by step", () => {
    expect(horizontalWindowIndex(0, 748)).toBe(0);
    expect(horizontalWindowIndex(373, 748)).toBe(0);
    expect(horizontalWindowIndex(374, 748)).toBe(1);
    expect(horizontalWindowIndex(1000, 748)).toBe(2);
    expect(horizontalWindowIndex(-200, 748)).toBe(0);
    expect(horizontalWindowIndex(Number.NaN, 748)).toBe(0);
  });

  it("spans two steps on each side plus the viewport", () => {
    expect(horizontalRenderWindow(horizontalWindowIndex(1000, 748), 748, 40000)).toEqual({
      x0: 0,
      x1: 2244,
    });
    expect(horizontalRenderWindow(10, 748, 40000)).toEqual({ x0: 2992, x1: 5236 });
    expect(horizontalRenderWindow(10, 748, 4000)).toEqual({ x0: 2992, x1: 4000 });
    expect(horizontalRenderWindow(0, 748, 500)).toEqual({ x0: 0, x1: 500 });
  });

  it("stays within the lane when the index is stale", () => {
    expect(horizontalRenderWindow(50, 748, 2000)).toEqual({ x0: 2000, x1: 2000 });
    expect(horizontalRenderWindow(3, 748, 0)).toEqual({ x0: 0, x1: 0 });
  });

  it("reads a viewport or a lane width that is not a number as 0, like the step does", () => {
    expect(horizontalRenderWindow(3, Number.NaN, 1000)).toEqual({ x0: 128, x1: 640 });
    expect(horizontalRenderWindow(3, Number.POSITIVE_INFINITY, 1000)).toEqual({ x0: 128, x1: 640 });
    expect(horizontalRenderWindow(0, 748, Number.NaN)).toEqual({ x0: 0, x1: 0 });
  });

  it("keeps a viewport of margin on the left and half a viewport on the right", () => {
    const failures: string[] = [];
    for (const viewport of [0, 1, 127, 128, 129, 200, 255, 256, 301, 748, 749, 1100, 1441]) {
      const step = horizontalWindowStep(viewport);
      for (const laneWidth of [viewport, 3 * viewport + 17, 40000]) {
        for (let scroll = 0; scroll <= laneWidth - viewport; scroll += 7) {
          const { x0, x1 } = horizontalRenderWindow(
            horizontalWindowIndex(scroll, viewport),
            viewport,
            laneWidth,
          );
          const ok =
            x0 >= 0 &&
            x0 <= x1 &&
            x1 <= laneWidth &&
            x0 <= Math.max(0, scroll - viewport) &&
            x1 >= Math.min(laneWidth, scroll + viewport + viewport / 2) &&
            x1 - x0 <= 4 * step + viewport;
          if (!ok) failures.push(`W ${viewport} lane ${laneWidth} at ${scroll}: ${x0}–${x1}`);
        }
      }
    }
    expect(failures).toEqual([]);
  });
});

describe("frameWindowOf", () => {
  it("adds a frame of margin on each side", () => {
    // f(100) = 24.19 and f(200) = 51.67 on the default lane.
    expect(frameWindowOf(g, { x0: 100, x1: 200 })).toEqual({ first: 23, last: 53 });
    expect(frameWindowOf(even, { x0: 33, x1: 51 })).toEqual({ first: 9, last: 21 });
  });

  it("clamps to the clip", () => {
    expect(frameWindowOf(g, { x0: 0, x1: 748 })).toEqual({ first: 0, last: 199 });
    expect(frameWindowOf(g, { x0: -500, x1: 5000 })).toEqual({ first: 0, last: 199 });
    expect(frameWindowOf(createTimelineGeometry(0, 748), { x0: 0, x1: 748 })).toEqual({
      first: 0,
      last: 0,
    });
    // The empty window of a stale index, at the lane's end.
    expect(frameWindowOf(g, { x0: 748, x1: 748 })).toEqual({ first: 199, last: 199 });
  });

  it("covers the whole render window of a long clip", () => {
    const long = createTimelineGeometry(17999, 403898);
    const pxWindow = horizontalRenderWindow(horizontalWindowIndex(200_000, 748), 748, 403898);
    const { first, last } = frameWindowOf(long, pxWindow);
    expect(frameToX(long, first)).toBeLessThan(pxWindow.x0);
    expect(frameToX(long, last)).toBeGreaterThan(pxWindow.x1);
    expect(last - first).toBeLessThan((pxWindow.x1 - pxWindow.x0) / long.pxPerFrame + 5);
  });
});

describe("snapEdge / snapCenter", () => {
  it.each([
    [10.3, 1, 10],
    [11.5, 1, 12],
    [10.3, 2, 10.5],
    [10.8, 2, 11],
    [10.3, 0, 10],
    [10.3, -2, 10],
    [10.3, Number.NaN, 10],
    [10.3, Number.POSITIVE_INFINITY, 10],
  ])("snaps %d at dpr %d to %d", (value, dpr, expected) => {
    expect(snapEdge(value, dpr)).toBe(expected);
  });

  it.each([
    [12, 3, 1, 12.5],
    [62, 2, 1, 62],
    [12, 3, 2, 12],
    [10.3, 3, 1, 10.5],
  ])("centers a mark at %d, %d px wide, at dpr %d on %d", (x, width, dpr, expected) => {
    expect(snapCenter(x, width, dpr)).toBe(expected);
  });

  it("puts the left edge on the grid at a fractional dpr", () => {
    expect(snapCenter(12, 2, 1.5)).toBeCloseTo(12 + 1 / 3, 9);
  });
});

describe("zoomAnchorFrame", () => {
  // Scrolled to 40 with a 100 px viewport: x 40 to 140, frames 14 to 64.
  it("anchors on the playhead while it is in view, edges included", () => {
    expect(zoomAnchorFrame(even, 40, 100, 30)).toBe(30);
    expect(zoomAnchorFrame(even, 40, 100, 14)).toBe(14);
    expect(zoomAnchorFrame(even, 40, 100, 64)).toBe(64);
  });

  it("anchors on the viewport center otherwise, fractional frames allowed", () => {
    expect(zoomAnchorFrame(even, 40, 100, 13)).toBe(39);
    expect(zoomAnchorFrame(even, 40, 100, 65)).toBe(39);
    expect(zoomAnchorFrame(even, 41, 100, 99)).toBe(39.5);
    expect(zoomAnchorFrame(even, 40, 100, Number.NaN)).toBe(39);
  });
});

describe("anchoredScrollLeft", () => {
  it("keeps the anchor frame at the same screen x", () => {
    expect(anchoredScrollLeft(g, zoomed, 0, 100, 748)).toBeCloseTo(
      12 + (100 * 7456) / 199 - (12 + (100 * 724) / 199),
      6,
    );
    expect(anchoredScrollLeft(g, zoomed, 0, 100, 748)).toBeCloseTo(3382.91, 2);
    // Frame 30 is 52 px into the view at 2 px per frame; at 4 px per frame it is at 132.
    expect(anchoredScrollLeft(even, createTimelineGeometry(100, 424), 20, 30, 100)).toBe(80);
  });

  it("clamps to the scroll range", () => {
    expect(anchoredScrollLeft(g, zoomed, 0, 199, 748)).toBeCloseTo(6732, 6);
    expect(anchoredScrollLeft(zoomed, g, 3000, 100, 748)).toBe(0);
    expect(anchoredScrollLeft(g, g, 50, 100, 748)).toBe(0);
    expect(anchoredScrollLeft(g, zoomed, 0, Number.NaN, 748)).toBe(0);
  });

  it("stays in [0, 6732] and keeps the anchor in place unless clamped", () => {
    const failures: string[] = [];
    for (const prev of [g, createTimelineGeometry(199, 1870)]) {
      for (let scroll = 0; scroll <= prev.laneWidth - 748; scroll += 11) {
        for (let anchor = -20; anchor <= 220; anchor += 0.5) {
          const next = anchoredScrollLeft(prev, zoomed, scroll, anchor, 748);
          const unclamped = frameToX(zoomed, anchor) - (frameToX(prev, anchor) - scroll);
          const expected = Math.min(6732, Math.max(0, unclamped));
          if (next < 0 || next > 6732 || Math.abs(next - expected) > 1e-6) {
            failures.push(`lane ${prev.laneWidth}, scroll ${scroll}, anchor ${anchor}: ${next}`);
          }
        }
      }
    }
    expect(failures).toEqual([]);
  });

  it("keeps a visible playhead still across a zoom", () => {
    const scroll = 3000;
    const anchor = zoomAnchorFrame(zoomed, scroll, 748, 85);
    const twice = createTimelineGeometry(199, 14960);
    const next = anchoredScrollLeft(zoomed, twice, scroll, anchor, 748);
    expect(anchor).toBe(85);
    expect(frameToX(twice, 85) - next).toBeCloseTo(frameToX(zoomed, 85) - scroll, 6);
  });
});

describe("revealScrollLeft", () => {
  // 12 px per frame and a 400 px viewport: from scroll 0, frames 1 to 30 show 24 px inside.
  it("leaves a frame that shows at least the margin inside the viewport", () => {
    expect(revealScrollLeft(wide, 0, 400, 10)).toBeNull();
    expect(revealScrollLeft(wide, 0, 400, 1)).toBeNull();
    expect(revealScrollLeft(wide, 0, 400, 30)).toBeNull();
    expect(revealScrollLeft(wide, 0, 400, 31, 0)).toBeNull();
  });

  it("pages an off-screen frame to a quarter of the viewport", () => {
    expect(revealScrollLeft(wide, 0, 400, 31)).toBe(284);
    expect(revealScrollLeft(wide, 0, 400, 50)).toBe(512);
    expect(frameToX(wide, 50) - 512).toBe(100);
  });

  it("clamps to the scroll range, and returns null when that does not move", () => {
    expect(revealScrollLeft(wide, 512, 400, 0)).toBe(0);
    expect(revealScrollLeft(wide, 100.5, 400, 0)).toBe(0);
    expect(revealScrollLeft(wide, 0, 400, 0)).toBeNull();
    expect(revealScrollLeft(wide, 0, 400, 100)).toBe(824);
    expect(revealScrollLeft(wide, 824, 400, 100)).toBeNull();
    expect(revealScrollLeft(createTimelineGeometry(100, 400), 0, 400, 99)).toBeNull();
  });

  it("reveals nothing for a frame that is not a number", () => {
    expect(revealScrollLeft(wide, 0, 400, Number.NaN)).toBeNull();
  });

  it("pages every frame in a viewport narrower than its two margins", () => {
    // x(1) = 24 meets the left margin, but the visible band [24, 16] is empty.
    expect(revealScrollLeft(wide, 0, 40, 1)).toBe(14);
  });
});

describe("playhead badge", () => {
  it("is 7 px of padding on each side of the frame digits", () => {
    expect(badgeWidthForFrame(0)).toBeCloseTo(20.6, 9);
    expect(badgeWidthForFrame(199)).toBeCloseTo(33.8, 9);
    expect(badgeWidthForFrame(17999)).toBeCloseTo(47, 9);
    expect(badgeWidthForFrame(99.6)).toBeCloseTo(33.8, 9);
    expect(badgeWidthForFrame(5, 7)).toBe(21);
  });

  it("centers on the playhead", () => {
    expect(playheadBadgeLeft(even, 50, 20)).toBe(102);
  });

  it("stays inside the lane on the first and the last frame", () => {
    expect(playheadBadgeLeft(g, 0, badgeWidthForFrame(0))).toBeCloseTo(1.7, 9);
    expect(playheadBadgeLeft(g, 199, badgeWidthForFrame(199))).toBeCloseTo(748 - 33.8, 9);
    expect(playheadBadgeLeft(g, 0, 40)).toBe(0);
    const long = createTimelineGeometry(17999, 748);
    expect(playheadBadgeLeft(long, 0, badgeWidthForFrame(0))).toBeGreaterThanOrEqual(0);
    expect(playheadBadgeLeft(long, 17999, badgeWidthForFrame(17999))).toBe(748 - 47);
    expect(playheadBadgeLeft(createTimelineGeometry(9, 20), 9, 33.8)).toBe(0);
  });

  it("never leaves the lane, and stays centered when it can", () => {
    const failures: number[] = [];
    for (let frame = 0; frame <= 199; frame += 1) {
      const width = badgeWidthForFrame(frame);
      const left = playheadBadgeLeft(g, frame, width);
      const centered = Math.abs(left + width / 2 - frameToX(g, frame)) < 1e-9;
      const clamped = left === 0 || left === 748 - width;
      if (left < 0 || left > 748 - width || !(centered || clamped)) failures.push(frame);
    }
    expect(failures).toEqual([]);
  });
});
