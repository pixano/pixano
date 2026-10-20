/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { buildDensityBuckets, densityBucketCount } from "../densityBuckets";

const span = (start: number, end: number) => ({ start, end });
const counts = (spans: { start: number; end: number }[], frameCount: number) =>
  buildDensityBuckets(spans, frameCount).map((bucket) => bucket.count);

/** The indexes of the buckets that count at least one span. */
const litBuckets = (spans: { start: number; end: number }[], frameCount: number) =>
  counts(spans, frameCount).flatMap((count, index) => (count > 0 ? [index] : []));

describe("densityBucketCount", () => {
  it("clamps the frame count to 48…180", () => {
    expect(densityBucketCount(2)).toBe(48);
    expect(densityBucketCount(30)).toBe(48);
    expect(densityBucketCount(47)).toBe(48);
    expect(densityBucketCount(48)).toBe(48);
    expect(densityBucketCount(49)).toBe(49);
    expect(densityBucketCount(100)).toBe(100);
    expect(densityBucketCount(179)).toBe(179);
    expect(densityBucketCount(180)).toBe(180);
    expect(densityBucketCount(181)).toBe(180);
    expect(densityBucketCount(18_000)).toBe(180);
  });

  it("is 1 for a clip of one frame or less", () => {
    expect(densityBucketCount(1)).toBe(1);
    expect(densityBucketCount(0)).toBe(1);
    expect(densityBucketCount(-5)).toBe(1);
    expect(densityBucketCount(Number.NaN)).toBe(1);
  });
});

describe("buildDensityBuckets", () => {
  it("makes densityBucketCount buckets, indexed in order", () => {
    for (const frameCount of [1, 2, 30, 100, 200, 18_000]) {
      const buckets = buildDensityBuckets([], frameCount);
      expect(buckets).toHaveLength(densityBucketCount(frameCount));
      expect(buckets.map((bucket) => bucket.index)).toEqual(buckets.map((_, index) => index));
    }
  });

  it("counts a span over the whole clip once in every bucket", () => {
    for (const frameCount of [1, 2, 7, 30, 47, 48, 100, 181, 200, 18_000]) {
      const all = counts([span(0, frameCount - 1)], frameCount);
      expect(all).toEqual(all.map(() => 1));
    }
  });

  it("counts each span covering a bucket", () => {
    // 100 frames: one bucket per frame.
    const result = counts([span(0, 9), span(5, 14), span(5, 5)], 100);
    expect(result.slice(0, 16)).toEqual([1, 1, 1, 1, 1, 3, 2, 2, 2, 2, 1, 1, 1, 1, 1, 0]);
    expect(result.slice(16).every((count) => count === 0)).toBe(true);
  });

  it("puts a frame in the bucket of its cell's left edge, buckets a frame wide or more", () => {
    // 200 frames in 180 buckets of 10/9 frame: floor(5 / (10/9)) = 4.
    expect(litBuckets([span(0, 5)], 200)).toEqual([0, 1, 2, 3, 4]);
    expect(litBuckets([span(6, 6)], 200)).toEqual([5]);
    // Bucket 30 of 186 frames starts on frame 31; 31 / (186 / 180) rounds to 29.999…
    expect(litBuckets([span(31, 31)], 186)).toEqual([30]);
  });

  it("covers every bucket a frame's cell touches when buckets are narrower than a frame", () => {
    // 30 frames in 48 buckets of 0.625 frame; frame f covers [f - 0.5, f + 0.5].
    expect(litBuckets([span(0, 0)], 30)).toEqual([0, 1]);
    expect(litBuckets([span(10, 10)], 30)).toEqual([16, 17]);
    expect(litBuckets([span(29, 29)], 30)).toEqual([46, 47]);
    // Two frames in 48 buckets: each frame takes half the strip.
    expect(litBuckets([span(1, 1)], 2)).toEqual(Array.from({ length: 24 }, (_, i) => 24 + i));
  });

  it("smooths a lone bucket with weights 1, 2, 3, 2, 1", () => {
    const buckets = buildDensityBuckets([span(50, 50)], 100);
    expect(buckets.map((bucket) => bucket.count).filter((count) => count > 0)).toEqual([1]);
    expect(buckets[50].count).toBe(1);

    const expected = [1 / 9, 2 / 9, 3 / 9, 2 / 9, 1 / 9];
    buckets
      .slice(48, 53)
      .forEach((bucket, i) => expect(bucket.smoothed).toBeCloseTo(expected[i], 12));
    for (const bucket of [...buckets.slice(0, 48), ...buckets.slice(53)]) {
      expect(bucket.smoothed).toBe(0);
    }
  });

  it("smooths the end buckets over the neighbors that exist", () => {
    const first = buildDensityBuckets([span(0, 0)], 100);
    expect(first[0].smoothed).toBeCloseTo(3 / 6, 12);
    expect(first[1].smoothed).toBeCloseTo(2 / 8, 12);
    expect(first[2].smoothed).toBeCloseTo(1 / 9, 12);
    expect(first[3].smoothed).toBe(0);

    const last = buildDensityBuckets([span(99, 99)], 100);
    expect(last[99].smoothed).toBeCloseTo(3 / 6, 12);
    expect(last[98].smoothed).toBeCloseTo(2 / 8, 12);
    expect(last[97].smoothed).toBeCloseTo(1 / 9, 12);

    expect(buildDensityBuckets([span(0, 0)], 1)[0].smoothed).toBe(1);
  });

  it("keeps a sparse strip dim: the scale is at least 1", () => {
    const buckets = buildDensityBuckets([span(50, 50)], 100);
    expect(buckets[50].normalized).toBeCloseTo(0.38, 12);
    expect(buckets[49].normalized).toBeCloseTo(0.28, 12);
    expect(buckets[51].normalized).toBeCloseTo(0.28, 12);
    expect(buckets[48].normalized).toBeCloseTo(0.18, 12);
    expect(buckets[0].normalized).toBe(0.08);
    expect(buildDensityBuckets([], 100).every((bucket) => bucket.normalized === 0.08)).toBe(true);
  });

  it("normalizes to 0.08…0.98, the largest smoothed count at 0.98", () => {
    // Counts 2 everywhere, 3 over frames 40 to 60.
    const buckets = buildDensityBuckets([span(0, 99), span(0, 99), span(40, 60)], 100);
    expect(buckets[50].smoothed).toBe(3);
    expect(buckets[50].normalized).toBe(0.98);
    expect(buckets[10].normalized).toBeCloseTo(0.08 + (0.9 * 2) / 3, 12);
    expect(Math.max(...buckets.map((bucket) => bucket.normalized))).toBe(0.98);

    const mixed = buildDensityBuckets(
      [span(0, 30), span(10, 12), span(10, 80), span(11, 11), span(150, 199)],
      200,
    );
    for (const bucket of mixed) {
      expect(bucket.normalized).toBeGreaterThanOrEqual(0.08);
      expect(bucket.normalized).toBeLessThanOrEqual(0.98);
    }
    expect(Math.max(...mixed.map((bucket) => bucket.normalized))).toBe(0.98);
  });

  it("clamps spans to the clip", () => {
    expect(litBuckets([span(-20, 10)], 100)).toEqual(Array.from({ length: 11 }, (_, i) => i));
    expect(litBuckets([span(90, 500)], 100)).toEqual(Array.from({ length: 10 }, (_, i) => 90 + i));
    expect(litBuckets([span(200, 300)], 100)).toEqual([]);
    expect(litBuckets([span(-50, -1)], 100)).toEqual([]);
    expect(litBuckets([span(0, 5)], 1)).toEqual([0]);
  });

  it("puts the bucket edges half a frame before each frame's center", () => {
    const perFrame = buildDensityBuckets([], 100);
    expect(perFrame[0]).toMatchObject({ startFrame: -0.5, endFrame: 0.5 });
    expect(perFrame[42]).toMatchObject({ startFrame: 41.5, endFrame: 42.5 });

    const wide = buildDensityBuckets([], 200);
    expect(wide[0].startFrame).toBe(-0.5);
    expect(wide[0].endFrame).toBeCloseTo(200 / 180 - 0.5, 12);
    expect(wide[179].endFrame).toBe(199.5);
    wide.slice(1).forEach((bucket, i) => expect(bucket.startFrame).toBe(wide[i].endFrame));

    const narrow = buildDensityBuckets([], 30);
    expect(narrow[0].startFrame).toBe(-0.5);
    expect(narrow[47]).toMatchObject({ startFrame: 28.875, endFrame: 29.5 });
    narrow.slice(1).forEach((bucket, i) => expect(bucket.startFrame).toBe(narrow[i].endFrame));

    expect(buildDensityBuckets([], 1)).toEqual([
      { index: 0, count: 0, smoothed: 0, normalized: 0.08, startFrame: -0.5, endFrame: 0.5 },
    ]);
  });

  it("counts a frame only in buckets its cell [f - 0.5, f + 0.5] overlaps", () => {
    for (const frameCount of [2, 30, 47, 48, 100, 200, 1000]) {
      const buckets = buildDensityBuckets([], frameCount);
      for (const frame of [0, 1, Math.floor(frameCount / 3), frameCount - 1]) {
        const lit = litBuckets([span(frame, frame)], frameCount);
        expect(lit.length).toBeGreaterThan(0);
        for (const index of lit) {
          expect(buckets[index].startFrame).toBeLessThan(frame + 0.5);
          expect(buckets[index].endFrame).toBeGreaterThan(frame - 0.5);
        }
      }
    }
  });

  it("takes the spans from any iterable", () => {
    function* spans() {
      yield span(0, 9);
      yield span(5, 14);
    }
    expect(counts([...spans()], 100)).toEqual(
      buildDensityBuckets(spans(), 100).map((bucket) => bucket.count),
    );
    expect(buildDensityBuckets(new Set([span(0, 99)]), 100).every((b) => b.count === 1)).toBe(true);
  });

  it("treats an unusable frame count as a one-frame clip", () => {
    const one = buildDensityBuckets([span(0, 0)], 1);
    expect(buildDensityBuckets([span(0, 0)], 0)).toEqual(one);
    expect(buildDensityBuckets([span(0, 0)], Number.NaN)).toEqual(one);
    expect(buildDensityBuckets([span(0, 0)], Number.POSITIVE_INFINITY)).toEqual(one);
  });
});
