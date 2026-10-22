/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * The tracklet-density strip under the timeline ruler: how many presence spans cover each slice
 * of the clip, smoothed over the neighboring slices and normalized for a color ramp. Bucket
 * edges are fractional frames shifted by half a frame, so the strip lines up with `frameToX`.
 */

const SMOOTHING_RADIUS = 2;
const NORMALIZED_MIN = 0.08;
const NORMALIZED_SPAN = 0.9;

/** The number of buckets of a clip: 1 up to one frame, else the frame count clamped to 48…180. */
export function densityBucketCount(frameCount: number): number {
  const frames = Math.floor(frameCount);
  return frames > 1 ? Math.max(48, Math.min(frames, 180)) : 1;
}

/** One slice of the density strip. */
export interface DensityBucket {
  readonly index: number;
  /** The spans that cover the bucket. */
  readonly count: number;
  /** `count` averaged over the two buckets on each side, with weights 1, 2, 3, 2, 1. */
  readonly smoothed: number;
  /** `smoothed` over the largest one (at least 1), mapped to 0.08…0.98, for the color ramp. */
  readonly normalized: number;
  /** The left edge, in fractional frames (the first bucket starts at -0.5). */
  readonly startFrame: number;
  /** The right edge, in fractional frames: the next bucket's `startFrame`. */
  readonly endFrame: number;
}

/** The density buckets of a clip of `frameCount` frames, from inclusive presence spans. */
export function buildDensityBuckets(
  spans: Iterable<{ readonly start: number; readonly end: number }>,
  frameCount: number,
): DensityBucket[] {
  const frames = Number.isFinite(frameCount) ? Math.max(1, Math.floor(frameCount)) : 1;
  const bucketCount = densityBucketCount(frames);
  // With buckets narrower than a frame, a span runs to the last bucket its end frame touches:
  // some buckets hold no frame start, and would never count anything.
  const narrow = bucketCount > frames;
  const counts = new Array<number>(bucketCount).fill(0);
  for (const { start, end } of spans) {
    const first = Math.max(0, Math.floor((start * bucketCount) / frames));
    const last = Math.min(
      bucketCount - 1,
      narrow
        ? Math.ceil(((end + 1) * bucketCount) / frames) - 1
        : Math.floor((end * bucketCount) / frames),
    );
    for (let index = first; index <= last; index++) counts[index] += 1;
  }

  const smoothed = counts.map((_, index) => {
    let weightedSum = 0;
    let totalWeight = 0;
    for (let offset = -SMOOTHING_RADIUS; offset <= SMOOTHING_RADIUS; offset++) {
      const neighbor = index + offset;
      if (neighbor < 0 || neighbor >= bucketCount) continue;
      const weight = SMOOTHING_RADIUS + 1 - Math.abs(offset);
      weightedSum += counts[neighbor] * weight;
      totalWeight += weight;
    }
    return weightedSum / totalWeight;
  });

  const scale = Math.max(1, ...smoothed);
  return counts.map((count, index) => ({
    index,
    count,
    smoothed: smoothed[index],
    normalized: NORMALIZED_MIN + NORMALIZED_SPAN * Math.min(1, smoothed[index] / scale),
    startFrame: (index * frames) / bucketCount - 0.5,
    endFrame: ((index + 1) * frames) / bucketCount - 0.5,
  }));
}
