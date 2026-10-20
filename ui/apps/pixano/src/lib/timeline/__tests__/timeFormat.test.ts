/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { formatFps, formatTimecode, fpsFromSequenceFrames, frameTime } from "../timeFormat";

const frames = (indexes: number[], fps: number) =>
  indexes.map((frame_index) => ({ data: { frame_index, timestamp: frame_index / fps } }));

describe("formatTimecode", () => {
  it("formats minutes, seconds and milliseconds", () => {
    expect(formatTimecode(0)).toBe("00:00.000");
    expect(formatTimecode(4.3667)).toBe("00:04.367");
    expect(formatTimecode(frameTime(131, 30))).toBe("00:04.367");
    expect(formatTimecode(125.4, 1)).toBe("02:05.4");
  });

  it("carries a rounded fraction into the seconds and minutes", () => {
    expect(formatTimecode(59.9996)).toBe("01:00.000");
    expect(formatTimecode(0.9996, 2)).toBe("00:01.00");
  });

  it("shows hours from one hour on", () => {
    expect(formatTimecode(3661.5, 1)).toBe("1:01:01.5");
    expect(formatTimecode(3599.9996)).toBe("1:00:00.000");
  });

  it("honours the number of decimals", () => {
    expect(formatTimecode(5, 0)).toBe("00:05");
    expect(formatTimecode(1.5, 1)).toBe("00:01.5");
    expect(formatTimecode(0.15, 2)).toBe("00:00.15");
  });

  it("clamps negative and non-finite times to zero", () => {
    expect(formatTimecode(-1)).toBe("00:00.000");
    expect(formatTimecode(Number.NaN)).toBe("00:00.000");
    expect(formatTimecode(Number.POSITIVE_INFINITY, 1)).toBe("00:00.0");
  });
});

describe("frameTime", () => {
  it("divides by the frame rate", () => {
    expect(frameTime(30, 30)).toBe(1);
    expect(frameTime(131, 30)).toBeCloseTo(4.366667, 6);
  });

  it("is zero without a usable frame rate", () => {
    expect(frameTime(30, 0)).toBe(0);
    expect(frameTime(30, Number.NaN)).toBe(0);
  });
});

describe("fpsFromSequenceFrames", () => {
  it("reads the rate from the frame indexes and timestamps", () => {
    expect(fpsFromSequenceFrames(frames([0, 1, 2, 3, 4], 25))).toBeCloseTo(25, 9);
    const ntsc = Array.from({ length: 200 }, (_, i) => ({
      data: { frame_index: i, timestamp: (i * 1001) / 30000 },
    }));
    expect(fpsFromSequenceFrames(ntsc)).toBeCloseTo(29.97003, 5);
  });

  it("keeps the rate of a view with missing frames", () => {
    // Counting frames instead of indexes would give 3 / (4/30) = 22.5.
    expect(fpsFromSequenceFrames(frames([0, 1, 2, 4], 30))).toBeCloseTo(30, 9);
  });

  it("falls back to the frame count when indexes are missing", () => {
    const timestamps = [0, 0.2, 0.5, 0.7].map((timestamp) => ({ data: { timestamp } }));
    expect(fpsFromSequenceFrames(timestamps)).toBeCloseTo(3 / 0.7, 9);
  });

  it("is undefined when the rate cannot be known", () => {
    expect(fpsFromSequenceFrames([])).toBeUndefined();
    expect(fpsFromSequenceFrames(frames([0], 30))).toBeUndefined();
    const unstamped = [0, 1, 2].map((frame_index) => ({ data: { frame_index, timestamp: 0 } }));
    expect(fpsFromSequenceFrames(unstamped)).toBeUndefined();
  });
});

describe("formatFps", () => {
  it("keeps two decimals at most and drops trailing zeros", () => {
    expect(formatFps(30)).toBe("30");
    expect(formatFps(30.0000001)).toBe("30");
    expect(formatFps(29.97002997)).toBe("29.97");
    expect(formatFps(23.976)).toBe("23.98");
    expect(formatFps(12.5)).toBe("12.5");
    expect(formatFps(24.000000000000004)).toBe("24");
  });
});
