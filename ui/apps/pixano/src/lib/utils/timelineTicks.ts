/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { formatTimecode } from "$lib/timeline/timeFormat";

export const MIN_TIMELINE_TICKS = 8;
export const MAX_TIMELINE_TICKS = 120;
const NICE_STEPS_SECONDS = [
  0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600,
];

/**
 * The "nice" tick step (seconds) for a clip of `totalSeconds` at a given zoom.
 * `zoomRatio` is the timeline surface width over its viewport width (1 when not
 * zoomed): the wanted tick count grows with it so the visible part always keeps
 * a few ticks, bounded by MIN/MAX for a sane DOM budget. The step whose count is
 * closest to that target wins, never one that yields fewer than MIN ticks.
 */
export function computeTickStepSeconds(totalSeconds: number, zoomRatio: number): number {
  const seconds = Math.max(1, Math.ceil(totalSeconds));
  const desiredTicks = Math.round(
    Math.min(MAX_TIMELINE_TICKS, Math.max(MIN_TIMELINE_TICKS, Math.ceil(5 * zoomRatio))),
  );

  let step = NICE_STEPS_SECONDS[NICE_STEPS_SECONDS.length - 1];
  let bestDiff = Number.POSITIVE_INFINITY;
  for (const candidate of NICE_STEPS_SECONDS) {
    const count = seconds / candidate;
    if (count < MIN_TIMELINE_TICKS) break;
    const diff = Math.abs(count - desiredTicks);
    if (diff < bestDiff) {
      bestDiff = diff;
      step = candidate;
    }
  }
  return step;
}

/** Tick positions (seconds) from 0 to the end of the clip, every `stepSeconds`. */
export function timelineTickSeconds(totalSeconds: number, stepSeconds: number): number[] {
  const seconds = Math.max(1, Math.ceil(totalSeconds));
  const ticks: number[] = [];
  for (let i = 0; i * stepSeconds <= seconds + 1e-9; i += 1) {
    ticks.push(i * stepSeconds);
  }
  return ticks;
}

/**
 * Label of the tick at `seconds`: `mm:ss`, plus as many decimals as the step has
 * for sub-second steps. Formatted from the tick's own time, never from a frame
 * index, so labels neither repeat nor land on frame boundaries.
 */
export function formatTickLabel(seconds: number, stepSeconds: number): string {
  if (stepSeconds >= 1) return formatTimecode(seconds, 0);
  const decimals = Math.min(3, String(stepSeconds).split(".")[1]?.length ?? 1) as 1 | 2 | 3;
  return formatTimecode(seconds, decimals);
}
