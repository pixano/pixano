/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  computeTickStepSeconds,
  formatTickLabel,
  MIN_TIMELINE_TICKS,
  timelineTickSeconds,
} from "$lib/utils/timelineTicks";

describe("computeTickStepSeconds", () => {
  it("keeps at least the minimum tick count on a one-second clip", () => {
    const step = computeTickStepSeconds(1, 1);
    expect(timelineTickSeconds(1, step).length).toBeGreaterThanOrEqual(MIN_TIMELINE_TICKS);
    expect(step).toBe(0.1);
  });

  it("uses whole seconds on long clips and refines the step when zooming in", () => {
    expect(computeTickStepSeconds(600, 1)).toBe(60);
    expect(computeTickStepSeconds(600, 4)).toBe(30);
    expect(computeTickStepSeconds(600, 12)).toBe(10);
  });

  it("never picks a step that yields fewer ticks than the minimum", () => {
    for (const total of [1, 3, 17, 90, 3600]) {
      for (const zoom of [1, 2, 8, 40]) {
        const step = computeTickStepSeconds(total, zoom);
        expect(total / step).toBeGreaterThanOrEqual(MIN_TIMELINE_TICKS);
      }
    }
  });
});

describe("formatTickLabel", () => {
  it("labels sub-second ticks from their own time, with the step's decimals", () => {
    // 100 ms/frame and 40 ms/frame used to quantise these to 00:00.0/00:00.1/00:00.1
    // and 00:00.04/00:00.08; the label no longer depends on the frame rate.
    expect([0.05, 0.1, 0.15, 0.2].map((s) => formatTickLabel(s, 0.05))).toEqual([
      "00:00.05",
      "00:00.10",
      "00:00.15",
      "00:00.20",
    ]);
    expect(formatTickLabel(0.5, 0.5)).toBe("00:00.5");
    expect(formatTickLabel(1.5, 0.5)).toBe("00:01.5");
  });

  it("labels whole-second ticks as mm:ss", () => {
    expect(formatTickLabel(0, 1)).toBe("00:00");
    expect(formatTickLabel(65, 5)).toBe("01:05");
  });

  it("gives every tick of a sub-second ladder a distinct label", () => {
    const labels = timelineTickSeconds(1, 0.05).map((s) => formatTickLabel(s, 0.05));
    expect(new Set(labels).size).toBe(labels.length);
  });
});
