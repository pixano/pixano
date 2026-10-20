/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * A lane's marks inside the render window: presence lines, keyframe ticks, start/end caps, and
 * bands where ticks would sit closer than a few px. Built as lane-px numbers, then as SVG path
 * data. Binary searches keep the work to O(log n) plus the keyframes in the window.
 */

import { keyframeColorAt, lowerBound, upperBound } from "./laneQueries";
import { frameToX, snapCenter, snapEdge } from "./timelineGeometry";
import type {
  FrameWindow,
  LaneGeom,
  MarkBox,
  MarkGeometry,
  PxWindow,
  TimelineGeometry,
} from "./types";

/** Keyframes closer than this, in px, merge into a band. */
export const TICK_MERGE_PX = 3;

/** One color's marks in lane px: flat [x0, x1] pairs for lines and bands, centers for the rest. */
export interface MarkGroup {
  readonly color: string;
  readonly lines: number[];
  readonly bands: number[];
  readonly ticks: number[];
  readonly caps: number[];
}

/** What `buildLaneMarks` draws besides the lines and caps. */
export interface LaneMarksOptions {
  /** Draw the keyframe ticks and bands. */
  readonly showTicks: boolean;
  /** Keyframes closer than this, in px, merge into a band (default `TICK_MERGE_PX`). */
  readonly mergePx?: number;
}

/** The SVG path data of one mark group. */
export interface LanePathData {
  readonly lines: string;
  readonly bands: string;
  readonly ticks: string;
  readonly caps: string;
}

/** The marks of a lane inside a window, one group per color in order of first appearance. */
export function buildLaneMarks(
  lane: LaneGeom,
  geometry: TimelineGeometry,
  frameWindow: FrameWindow,
  pxWindow: PxWindow,
  options: LaneMarksOptions,
): MarkGroup[] {
  const groups = new Map<string, MarkGroup>();
  const { first, last } = frameWindow;

  for (const span of lane.spans) {
    if (span.end < first || span.start > last) continue;
    const x0 = Math.max(frameToX(geometry, span.start), pxWindow.x0);
    const x1 = Math.min(frameToX(geometry, span.end), pxWindow.x1);
    if (x1 > x0) groupOf(groups, span.color).lines.push(x0, x1);
  }

  const caps = lane.capFrames;
  for (let index = lowerBound(caps, first); index < caps.length && caps[index] <= last; index++) {
    const frame = caps[index];
    groupOf(groups, keyframeColorAt(lane, frame)).caps.push(frameToX(geometry, frame));
  }

  if (options.showTicks) {
    addTicks(groups, lane, geometry, frameWindow, options.mergePx ?? TICK_MERGE_PX);
  }
  return [...groups.values()];
}

/** A mark group as SVG path data, in px from `xOffset` (the SVG's left edge), snapped to `dpr`. */
export function lanePathData(
  group: MarkGroup,
  geo: MarkGeometry,
  dpr: number,
  xOffset: number,
): LanePathData {
  return {
    lines: rectanglesPath(group.lines, geo.line, dpr, xOffset),
    bands: rectanglesPath(group.bands, geo.tick, dpr, xOffset),
    ticks: capsulesPath(group.ticks, geo.tick, dpr, xOffset),
    caps: capsulesPath(group.caps, geo.cap, dpr, xOffset),
  };
}

function groupOf(groups: Map<string, MarkGroup>, color: string): MarkGroup {
  let group = groups.get(color);
  if (group === undefined) {
    group = { color, lines: [], bands: [], ticks: [], caps: [] };
    groups.set(color, group);
  }
  return group;
}

/**
 * Ticks and bands of the keyframes in the window plus one on each side, so a band cut by the
 * window ends out of sight. Caps are skipped and break runs.
 */
function addTicks(
  groups: Map<string, MarkGroup>,
  lane: LaneGeom,
  geometry: TimelineGeometry,
  frameWindow: FrameWindow,
  mergePx: number,
): void {
  const { frames, capFrames } = lane;
  const begin = Math.max(0, lowerBound(frames, frameWindow.first) - 1);
  const end = Math.min(frames.length, upperBound(frames, frameWindow.last) + 1);
  if (begin >= end) return;

  let cap = lowerBound(capFrames, frames[begin]);
  let inRun = false;
  let runFirst = 0;
  let runLast = 0;
  for (let index = begin; index < end; index++) {
    const frame = frames[index];
    while (cap < capFrames.length && capFrames[cap] < frame) cap++;
    const isCap = cap < capFrames.length && capFrames[cap] === frame;
    const joins = inRun && !isCap && (frame - runLast) * geometry.pxPerFrame < mergePx;
    if (inRun && !joins) {
      addRun(groups, lane, geometry, runFirst, runLast);
      inRun = false;
    }
    if (isCap) continue;
    if (!inRun) {
      inRun = true;
      runFirst = frame;
    }
    runLast = frame;
  }
  if (inRun) addRun(groups, lane, geometry, runFirst, runLast);
}

/** A run of one keyframe is a tick; a longer run is a band with a tick at each end. */
function addRun(
  groups: Map<string, MarkGroup>,
  lane: LaneGeom,
  geometry: TimelineGeometry,
  firstFrame: number,
  lastFrame: number,
): void {
  const group = groupOf(groups, keyframeColorAt(lane, firstFrame));
  const x0 = frameToX(geometry, firstFrame);
  group.ticks.push(x0);
  if (lastFrame === firstFrame) return;
  const x1 = frameToX(geometry, lastFrame);
  group.bands.push(x0, x1);
  groupOf(groups, keyframeColorAt(lane, lastFrame)).ticks.push(x1);
}

/** Rectangles from flat [x0, x1] pairs, spanning `box.y` to `box.y + box.h`. */
function rectanglesPath(pairs: number[], box: MarkBox, dpr: number, xOffset: number): string {
  const top = formatNumber(box.y);
  const bottom = formatNumber(box.y + box.h);
  let path = "";
  for (let index = 0; index + 1 < pairs.length; index += 2) {
    const left = formatNumber(snapEdge(pairs[index] - xOffset, dpr));
    const right = formatNumber(snapEdge(pairs[index + 1] - xOffset, dpr));
    path += `M${left} ${top}H${right}V${bottom}H${left}Z`;
  }
  return path;
}

/** Vertical segments, stroked `box.w` wide with round caps: `box.w` × `box.h` capsules. */
function capsulesPath(centers: number[], box: MarkBox, dpr: number, xOffset: number): string {
  const top = formatNumber(box.y + box.w / 2);
  const bottom = formatNumber(box.y + box.h - box.w / 2);
  let path = "";
  for (const x of centers) {
    path += `M${formatNumber(snapCenter(x - xOffset, box.w, dpr))} ${top}V${bottom}`;
  }
  return path;
}

/** A path number: three decimals at most, no trailing zeros. */
function formatNumber(value: number): string {
  return String(Math.round(value * 1000) / 1000);
}
