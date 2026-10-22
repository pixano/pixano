/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * The 44 px ruler band above the lanes: ticks on three levels, and a two-line label (the
 * time, then `#frame`) to the right of each major line. The major step is the first entry of
 * a ladder of frame counts and nice durations whose labels fit between two lines; the medium
 * and minor steps divide it. Marks are built for a frame window only, never the whole clip.
 */

import { formatTimecode, frameTime } from "./timeFormat";
import { frameToX, snapEdge } from "./timelineGeometry";
import type { FrameWindow, TimelineGeometry } from "./types";

/** Narrowest spacing of the minor ticks, in px (keyframe ticks closer than this merge too). */
export const RULER_MINOR_MIN_PX = 3;
/** Narrowest spacing of the medium ticks, in px. */
export const RULER_MEDIUM_MIN_PX = 12;
/** Distance from a major line to the left edge of its label, in px. */
export const RULER_LABEL_OFFSET_PX = 6;
/** Narrowest gap between the right edge of a label and the next major line, in px. */
export const RULER_LABEL_GAP_PX = 8;
/** The durations a major step may last, in seconds, ascending. */
export const NICE_DURATIONS_S: readonly number[] = Object.freeze([
  0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 18000, 36000,
]);

const FRAME_STEPS = [1, 2, 5, 10];
const TIME_DECIMALS = [0, 1, 2, 3] as const;
/** Room kept free at the right end of the lane: a label reaching into it is dropped. */
const LABEL_RIGHT_MARGIN_PX = 4;

/** The whole rate within 1 % of `fps` (29.97 → 30, 23.976 → 24), else `fps`; 1 when unusable. */
export function nominalFrameRate(fps: number): number {
  if (!(fps > 0) || !Number.isFinite(fps)) return 1;
  const rounded = Math.round(fps);
  return Math.abs(fps - rounded) <= 0.01 * fps ? rounded : fps;
}

/** The major steps, in frames, ascending: 1, 2, 5, 10 and the nice durations on whole frames. */
export function majorStepLadder(fps: number): number[] {
  const rate = nominalFrameRate(fps);
  const steps = new Set(FRAME_STEPS);
  for (const duration of NICE_DURATIONS_S) {
    const exact = duration * rate;
    const frames = Math.round(exact);
    if (frames >= 1 && Math.abs(frames - exact) <= 0.01 * exact) steps.add(frames);
  }
  return [...steps].sort((a, b) => a - b);
}

/** The fewest decimals (up to 3) that print the multiples of a step exactly in seconds; else 3. */
export function timeDecimalsForStep(stepFrames: number, fps: number): 0 | 1 | 2 | 3 {
  const seconds = stepFrames / nominalFrameRate(fps);
  return TIME_DECIMALS.find((decimals) => isWhole(seconds * 10 ** decimals)) ?? 3;
}

/** Character widths of the two label lines, in px. */
export interface RulerLabelMetrics {
  /** The time line (`00:01.0`). */
  readonly timeCharWidth: number;
  /** The frame line (`#30`). */
  readonly frameCharWidth: number;
}

/** JetBrains Mono at 11 px (time) and 10 px (frame), until the component measures the real ones. */
export const DEFAULT_RULER_LABEL_METRICS: RulerLabelMetrics = Object.freeze({
  timeCharWidth: 6.6,
  frameCharWidth: 6.0,
});

/**
 * The width of a clip's widest label: its time line, or its frame line when that is longer.
 * Hours count in the labels' own clock, the true rate (29.97 fps passes one hour before 30 fps
 * does), with as many digits as they take.
 */
export function rulerLabelWidth(
  decimals: number,
  lastFrame: number,
  fps: number,
  metrics: RulerLabelMetrics = DEFAULT_RULER_LABEL_METRICS,
): number {
  const hours = Math.floor(frameTime(lastFrame, fps) / 3600);
  const clockChars = hours >= 1 ? 6 + digitCount(hours) : 5;
  const timeChars = clockChars + (decimals > 0 ? decimals + 1 : 0);
  const frameChars = 1 + digitCount(lastFrame);
  return Math.max(timeChars * metrics.timeCharWidth, frameChars * metrics.frameCharWidth);
}

/** The ruler's steps in frames (null for a level too dense to draw) and its labels' decimals. */
export interface RulerLevels {
  /** Full-height lines, each with a label. */
  readonly major: number;
  readonly medium: number | null;
  readonly minor: number | null;
  readonly decimals: 0 | 1 | 2 | 3;
}

/**
 * The ruler's steps at a scale: the first ladder step whose labels fit between two major lines
 * (the last step, doubled until it fits, when none does), then the smallest ladder steps
 * dividing it that are at least 12 px (medium) and 3 px (minor) apart.
 */
export function chooseRulerLevels(
  pxPerFrame: number,
  fps: number,
  lastFrame: number,
  metrics: RulerLabelMetrics = DEFAULT_RULER_LABEL_METRICS,
): RulerLevels {
  const ladder = majorStepLadder(fps);
  const labelSpace = (step: number) =>
    rulerLabelWidth(timeDecimalsForStep(step, fps), lastFrame, fps, metrics) +
    RULER_LABEL_OFFSET_PX +
    RULER_LABEL_GAP_PX;
  let major = ladder.find((step) => step * pxPerFrame >= labelSpace(step));
  if (major === undefined) {
    major = ladder[ladder.length - 1];
    while (pxPerFrame > 0 && major * pxPerFrame < labelSpace(major)) major *= 2;
  }
  const medium = smallestDividingStep(ladder, major, pxPerFrame, RULER_MEDIUM_MIN_PX);
  const minor = smallestDividingStep(ladder, medium ?? major, pxPerFrame, RULER_MINOR_MIN_PX);
  return { major, medium, minor, decimals: timeDecimalsForStep(major, fps) };
}

/** The label of a major line: the time over `#frame`, drawn from `x + RULER_LABEL_OFFSET_PX`. */
export interface RulerLabel {
  readonly frame: number;
  /** The major line's x, in lane px. */
  readonly x: number;
  readonly time: string;
  readonly frameText: string;
}

/** The ruler over a frame window: tick x in lane px (each frame on one level only), and labels. */
export interface RulerMarks {
  readonly minor: number[];
  readonly medium: number[];
  readonly major: number[];
  readonly labels: RulerLabel[];
}

/**
 * The ticks and labels of the ruler in a frame window, visiting only the multiples inside it.
 * Every major is labelled, except near the right end of the lane, where the label is dropped
 * and its line kept.
 */
export function buildRulerMarks(
  geometry: TimelineGeometry,
  fps: number,
  levels: RulerLevels,
  frameWindow: FrameWindow,
  metrics: RulerLabelMetrics = DEFAULT_RULER_LABEL_METRICS,
): RulerMarks {
  const { major, medium, minor, decimals } = levels;
  const first = Math.max(0, Math.ceil(frameWindow.first));
  const last = Math.min(geometry.lastFrame, Math.floor(frameWindow.last));
  const labelReach =
    RULER_LABEL_OFFSET_PX + rulerLabelWidth(decimals, geometry.lastFrame, fps, metrics);
  const marks: RulerMarks = { minor: [], medium: [], major: [], labels: [] };
  for (const frame of multiplesIn(major, first, last)) {
    const x = frameToX(geometry, frame);
    marks.major.push(x);
    if (x + labelReach > geometry.laneWidth - LABEL_RIGHT_MARGIN_PX) continue;
    const time = formatTimecode(frameTime(frame, fps), decimals);
    marks.labels.push({ frame, x, time, frameText: `#${frame}` });
  }
  for (const frame of multiplesIn(medium, first, last)) {
    if (frame % major !== 0) marks.medium.push(frameToX(geometry, frame));
  }
  for (const frame of multiplesIn(minor, first, last)) {
    if (frame % major !== 0 && (medium === null || frame % medium !== 0)) {
      marks.minor.push(frameToX(geometry, frame));
    }
  }
  return marks;
}

/** An SVG path of 1 px wide bars from `y0` to `y1`, one per x, left edges on the pixel grid. */
export function rulerRectPath(xs: readonly number[], y0: number, y1: number, dpr: number): string {
  const tail = ` ${formatPathNumber(y0)}h1v${formatPathNumber(y1 - y0)}h-1z`;
  let path = "";
  for (const x of xs) {
    if (Number.isFinite(x)) path += `M${formatPathNumber(snapEdge(x - 0.5, dpr))}${tail}`;
  }
  return path;
}

function isWhole(value: number): boolean {
  return Math.abs(value - Math.round(value)) <= 1e-9;
}

function digitCount(value: number): number {
  return String(Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0).length;
}

function smallestDividingStep(
  ladder: readonly number[],
  step: number,
  pxPerFrame: number,
  minPx: number,
): number | null {
  return ladder.find((d) => d < step && step % d === 0 && d * pxPerFrame >= minPx) ?? null;
}

/** The multiples of `step` from `first` to `last`; none unless the step is a finite number >= 1. */
function multiplesIn(step: number | null, first: number, last: number): number[] {
  const frames: number[] = [];
  if (step === null || !(step >= 1) || !Number.isFinite(step)) return frames;
  for (let frame = Math.ceil(first / step) * step; frame <= last; frame += step) frames.push(frame);
  return frames;
}

/** A path coordinate with at most 3 decimals and no trailing zeros. */
function formatPathNumber(value: number): string {
  return String(Math.round(value * 1000) / 1000);
}
