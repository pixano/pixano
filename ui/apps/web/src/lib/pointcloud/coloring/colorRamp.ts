/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Maps a normalised value to an RGB triple, written straight into a colour
 * buffer at `offset`.
 *
 * Writes rather than returns so a per-point loop over tens of thousands of
 * points allocates nothing — the same rule the Three.js scratch objects follow
 * elsewhere (docs/CODING_STANDARDS.md).
 */
export type ColorRamp = (t: number, out: Float32Array, offset: number) => void;

/** One anchor of a piecewise-linear ramp: a position in [0, 1] and its colour. */
interface RampStop {
  at: number;
  r: number;
  g: number;
  b: number;
}

/**
 * Stops of the shared scalar ramp: deep blue → cyan → green → yellow → red.
 *
 * The conventional lidar ramp, and the reason is not habit: it varies in hue
 * *and* lightness, so it stays readable both on the dark viewer background and
 * for a red-green colour-blind viewer, who still reads the blue-to-yellow half
 * of the range. A pure blue-to-red ramp collapses in exactly that case.
 */
const SCALAR_RAMP_STOPS: readonly RampStop[] = [
  { at: 0.0, r: 0.1, g: 0.15, b: 0.6 },
  { at: 0.25, r: 0.0, g: 0.65, b: 0.85 },
  { at: 0.5, r: 0.1, g: 0.8, b: 0.3 },
  { at: 0.75, r: 0.95, g: 0.85, b: 0.1 },
  { at: 1.0, r: 0.9, g: 0.15, b: 0.1 },
];

/**
 * The ramp for any mode colouring a continuous quantity (intensity, range, …).
 * Shared so two such modes are comparable at a glance instead of each inventing
 * its own palette.
 */
export const scalarRamp: ColorRamp = (t, out, offset) => {
  // NaN is possible from a degenerate normalisation; `!(t > 0)` catches it the
  // same way the bbox3d projection guard does, since every NaN comparison is
  // false and the plain `t < 0` form would let it through to the interpolation.
  const clamped = !(t > 0) ? 0 : t > 1 ? 1 : t;

  let upper = 1;
  while (upper < SCALAR_RAMP_STOPS.length - 1 && SCALAR_RAMP_STOPS[upper].at < clamped) upper++;
  const from = SCALAR_RAMP_STOPS[upper - 1];
  const to = SCALAR_RAMP_STOPS[upper];

  const span = to.at - from.at;
  const local = span > 0 ? (clamped - from.at) / span : 0;

  out[offset] = from.r + (to.r - from.r) * local;
  out[offset + 1] = from.g + (to.g - from.g) * local;
  out[offset + 2] = from.b + (to.b - from.b) * local;
};

/**
 * Shade for points a mode could not colour.
 *
 * Deliberately far darker than anything a mode produces. The first version sat
 * at 0.35 grey, which collided head-on with the camera-projection mode: sampled
 * street pixels average ~0.43 with almost no saturation, so "no camera saw this
 * point" and "a camera saw grey asphalt" rendered as the same shade and the
 * mode looked like it had done nothing. A value below the sampled range keeps
 * the two readable apart.
 */
export const UNCOLORED_R = 0.12;
export const UNCOLORED_G = 0.12;
export const UNCOLORED_B = 0.15;

export function writeUncolored(out: Float32Array, offset: number): void {
  out[offset] = UNCOLORED_R;
  out[offset + 1] = UNCOLORED_G;
  out[offset + 2] = UNCOLORED_B;
}

/** A ramp position per point, plus the values sitting at the ramp's landmarks. */
export interface EqualizedScale {
  /** Ramp input in [0, 1] for each point, parallel to the input array. */
  t: Float32Array;
  /** Value at the bottom of the ramp. */
  low: number;
  /** Value at the middle of the ramp — the distribution's median, by construction. */
  mid: number;
  /** Value at the top of the ramp. */
  high: number;
}

/**
 * Spreads a measured channel across the full ramp by **rank** rather than by
 * value: a point's colour is decided by what fraction of the cloud it exceeds.
 *
 * Stretching linearly between two bounds is the obvious approach and it fails
 * badly on every channel a lidar produces, because they are all heavily skewed.
 * On a nuScenes sweep the intensity median is 11 against a 99th percentile of
 * 100, and the range median is 6 m against 62 m — so a linear map leaves ~78%
 * of the cloud inside the bottom quarter of the ramp, which reads as a uniformly
 * blue cloud carrying no information. Equalising is what lidar viewers do, and
 * it guarantees the ramp is used evenly whatever the distribution's shape.
 *
 * The cost is that colour is no longer proportional to value, which is why the
 * scale reports `mid` alongside the bounds: under equalisation the ramp's
 * midpoint *is* the median, so a three-tick legend describes the mapping
 * exactly rather than implying a linearity that is not there.
 *
 * Ties share a rank, so a channel with one repeated value stays one flat colour
 * instead of being fanned out into a false gradient.
 */
export function equalize(values: Float32Array): EqualizedScale {
  const count = values.length;
  const t = new Float32Array(count);
  if (count === 0) return { t, low: 0, mid: 0, high: 0 };

  // Rank via a sorted copy of the indices: O(n log n) once per mode switch,
  // never per frame. `sort` on the index array keeps `values` untouched — it is
  // the parser's memoised channel, shared with every other reader.
  const order = Array.from({ length: count }, (_, i) => i);
  order.sort((a, b) => values[a] - values[b]);

  const lastIndex = count - 1;
  let rank = 0;
  while (rank < count) {
    // Consume the whole run of equal values, then give them all the same
    // position: distinct colours for identical measurements would be invented
    // detail, and it is what makes a uniform channel render flat.
    let end = rank;
    while (end + 1 < count && values[order[end + 1]] === values[order[rank]]) end++;
    const shared = lastIndex > 0 ? (rank + end) / 2 / lastIndex : 0;
    for (let i = rank; i <= end; i++) t[order[i]] = shared;
    rank = end + 1;
  }

  return {
    t,
    low: values[order[0]],
    mid: values[order[lastIndex >> 1]],
    high: values[order[lastIndex]],
  };
}
