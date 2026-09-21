/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { equalize, scalarRamp } from "../colorRamp.js";
import { elevationColorMode } from "../modes/elevationColorMode.js";
import { intensityColorMode } from "../modes/intensityColorMode.js";
import { rangeColorMode } from "../modes/rangeColorMode.js";
import {
  colorAt,
  expectColorAt,
  makeColorBuffer,
  makeColorSource,
  worldToSensorAt,
} from "./fakeColorSource.js";

const NO_ABORT = new AbortController().signal;

/** Colour the whole cloud with one mode and hand back the buffer. */
async function color(
  mode: typeof elevationColorMode,
  source: ReturnType<typeof makeColorSource>,
): Promise<Float32Array> {
  const out = makeColorBuffer(source.pointCount);
  await mode.computeColors(source, out, NO_ABORT);
  return out;
}

/** How many of the cloud's points land in the bottom quarter of the ramp. */
async function fractionInBottomQuarter(
  mode: typeof elevationColorMode,
  source: ReturnType<typeof makeColorSource>,
): Promise<number> {
  const colors = await color(mode, source);
  const low = new Float32Array(3);
  scalarRamp(0.25, low, 0);
  let count = 0;
  for (let i = 0; i < source.pointCount; i++) {
    // The ramp is blue-dominated below t=0.25; comparing the blue channel
    // against the colour at exactly 0.25 is a stable proxy for "still blue".
    if (colorAt(colors, i)[2] >= low[2]) count++;
  }
  return count / source.pointCount;
}

/**
 * A skewed channel, shaped like the real thing: most points bunched low, a
 * long thin tail. This is what made every scalar mode render blue.
 */
function skewedCloud(valueAt: (v: number) => [number, number, number, number]) {
  const points = [
    ...Array.from({ length: 90 }, (_, i) => valueAt(i / 90)),
    ...Array.from({ length: 10 }, (_, i) => valueAt(10 + i * 9)),
  ];
  return makeColorSource(points as never);
}

// ─── Equalisation, shared by every scalar mode ───────────────────────────────

describe("equalize", () => {
  it("returns an empty scale for an empty channel", () => {
    const scale = equalize(new Float32Array(0));
    expect(scale.t.length).toBe(0);
    expect(scale).toMatchObject({ low: 0, mid: 0, high: 0 });
  });

  it("puts the smallest value at the bottom and the largest at the top", () => {
    const scale = equalize(Float32Array.from([5, 1, 9]));
    expect(scale.t[1]).toBeCloseTo(0);
    expect(scale.t[2]).toBeCloseTo(1);
  });

  it("spreads a skewed channel evenly across the ramp", () => {
    // The regression this exists for: 90 values bunched in [0,1] and a tail out
    // to 100. Linear normalisation left ~90% under t=0.1.
    const values = Float32Array.from([
      ...Array.from({ length: 90 }, (_, i) => i / 90),
      ...Array.from({ length: 10 }, (_, i) => 10 + i * 9),
    ]);
    const { t } = equalize(values);
    const belowQuarter = [...t].filter((v) => v < 0.25).length / t.length;
    expect(belowQuarter).toBeGreaterThan(0.2);
    expect(belowQuarter).toBeLessThan(0.3);
  });

  it("reports the median at the ramp's midpoint", () => {
    // What makes the three-tick legend truthful.
    const values = Float32Array.from([0, 1, 2, 100, 1000]);
    expect(equalize(values).mid).toBe(2);
  });

  it("gives equal values the same ramp position", () => {
    // Identical measurements must not be fanned into an invented gradient.
    const { t } = equalize(Float32Array.from([7, 3, 7, 3]));
    expect(t[0]).toBe(t[2]);
    expect(t[1]).toBe(t[3]);
  });

  it("keeps a uniform channel flat", () => {
    const { t } = equalize(new Float32Array(5).fill(4));
    expect(new Set([...t]).size).toBe(1);
  });

  it("leaves the caller's array untouched", () => {
    // It ranks the parser's memoised channel, shared with every other reader.
    const values = Float32Array.from([3, 1, 2]);
    equalize(values);
    expect([...values]).toEqual([3, 1, 2]);
  });
});

// ─── Elevation ────────────────────────────────────────────────────────────────

describe("elevationColorMode", () => {
  it("puts the lowest point at the bottom of the ramp", async () => {
    const colors = await color(
      elevationColorMode,
      makeColorSource([
        [0, 0, 0],
        [0, 0, 10],
      ]),
    );
    const bottom = new Float32Array(3);
    scalarRamp(0, bottom, 0);
    expectColorAt(colors, 0, [...bottom]);
  });

  it("reads height off the Lance Z axis, not Lance Y", async () => {
    // The parser maps Lance Z onto Three.js Y. Reading the wrong component
    // would still produce a plausible gradient, just of the wrong thing.
    const colors = await color(
      elevationColorMode,
      makeColorSource([
        [0, 10, 0],
        [0, 0, 10],
      ]),
    );
    expect(colorAt(colors, 0)).not.toEqual(colorAt(colors, 1));
    const top = new Float32Array(3);
    scalarRamp(1, top, 0);
    expectColorAt(colors, 1, [...top]); // Lance Z = 10 → highest
  });

  it("colours a flat cloud uniformly", async () => {
    const colors = await color(
      elevationColorMode,
      makeColorSource([
        [0, 0, 5],
        [1, 0, 5],
      ]),
    );
    expect(colorAt(colors, 0)).toEqual(colorAt(colors, 1));
  });

  it("does not leave a ground-dominated cloud in the bottom of the ramp", async () => {
    // The reported bug: a street sweep is nearly all ground, so a linear map
    // over the raw height span rendered the whole cloud one flat blue.
    const ground = skewedCloud((h) => [0, 0, h, 0]);
    expect(await fractionInBottomQuarter(elevationColorMode, ground)).toBeLessThan(0.45);
  });

  it("reports its legend as height above the lowest return", async () => {
    // Absolute world Z is an arbitrary number to a reader; height above ground
    // is not. The floor must therefore read as 0.
    const source = makeColorSource([
      [0, 0, -3],
      [0, 0, 2],
    ]);
    const result = await elevationColorMode.computeColors(
      source,
      makeColorBuffer(source.pointCount),
      NO_ABORT,
    );
    expect(result.legend?.low).toBeCloseTo(0);
    expect(result.legend?.high).toBeCloseTo(5);
    expect(result.legend?.unit).toBe("m");
  });
});

// ─── Intensity ────────────────────────────────────────────────────────────────

describe("intensityColorMode", () => {
  it("is unavailable when the intensity column is all zeros", () => {
    // The importer pads the stride when the sensor recorded no intensity;
    // saying so beats handing back a flat cloud that looks like a bug.
    const source = makeColorSource([
      [0, 0, 0, 0],
      [1, 1, 1, 0],
    ]);
    expect(intensityColorMode.unavailableReason?.(source)).toMatch(/no intensity/i);
  });

  it("is available as soon as one point carries intensity", () => {
    const source = makeColorSource([
      [0, 0, 0, 0],
      [1, 1, 1, 3],
    ]);
    expect(intensityColorMode.unavailableReason?.(source)).toBeNull();
  });

  it("does not report an empty cloud as lacking intensity", () => {
    expect(intensityColorMode.unavailableReason?.(makeColorSource([]))).toBeNull();
  });

  it("gives brighter returns the top of the ramp", async () => {
    const source = makeColorSource([
      [0, 0, 0, 0],
      [1, 0, 0, 100],
    ]);
    const colors = await color(intensityColorMode, source);
    const low = new Float32Array(3);
    const high = new Float32Array(3);
    scalarRamp(0, low, 0);
    scalarRamp(1, high, 0);
    expectColorAt(colors, 0, [...low]);
    expectColorAt(colors, 1, [...high]);
  });

  it("colours by intensity, not by position", async () => {
    // Two points at the same place with different returns must differ; the whole
    // point of the mode is to separate what geometry cannot.
    const source = makeColorSource([
      [0, 0, 0, 10],
      [0, 0, 0, 250],
    ]);
    const colors = await color(intensityColorMode, source);
    expect(colorAt(colors, 0)).not.toEqual(colorAt(colors, 1));
  });

  it("does not leave a low-intensity cloud in the bottom of the ramp", async () => {
    // The reported bug: real intensity has a median near 11 against a 99th
    // percentile of 100, so a linear map rendered four points in five blue.
    const skewed = skewedCloud((v) => [0, 0, 0, v]);
    expect(await fractionInBottomQuarter(intensityColorMode, skewed)).toBeLessThan(0.45);
  });

  it("reports a unitless three-point legend", async () => {
    const source = makeColorSource([
      [0, 0, 0, 1],
      [0, 0, 0, 4],
      [0, 0, 0, 9],
    ]);
    const result = await intensityColorMode.computeColors(
      source,
      makeColorBuffer(source.pointCount),
      NO_ABORT,
    );
    // Uncalibrated and scaled differently per sensor, so a unit would be a lie.
    expect(result.legend?.unit).toBeUndefined();
    expect(result.legend?.low).toBeCloseTo(1);
    expect(result.legend?.mid).toBeCloseTo(4);
    expect(result.legend?.high).toBeCloseTo(9);
  });
});

// ─── Distance to sensor ───────────────────────────────────────────────────────

describe("rangeColorMode", () => {
  it("measures from the origin when the cloud carries no pose", async () => {
    // A plain `PointCloud` is stored in the sensor frame, so the identity is the
    // correct transform rather than a degraded fallback.
    const source = makeColorSource([
      [1, 0, 0],
      [5, 0, 0],
      [10, 0, 0],
    ]);
    const result = await rangeColorMode.computeColors(
      source,
      makeColorBuffer(source.pointCount),
      NO_ABORT,
    );
    expect(result.legend?.low).toBeCloseTo(1);
    expect(result.legend?.high).toBeCloseTo(10);
  });

  it("measures from the sensor, not the world origin, on a calibrated cloud", async () => {
    // The case that makes this mode more than a norm: the points are in world
    // coordinates and the sensor is 100 m away, so distances must come out ~1
    // and ~2, not ~101 and ~102.
    const source = makeColorSource(
      [
        [101, 0, 0],
        [102, 0, 0],
      ],
      { worldToSensor: worldToSensorAt([100, 0, 0]) },
    );
    const result = await rangeColorMode.computeColors(
      source,
      makeColorBuffer(source.pointCount),
      NO_ABORT,
    );
    expect(result.legend?.low).toBeCloseTo(1);
    expect(result.legend?.high).toBeCloseTo(2);
  });

  it("accounts for all three axes", async () => {
    const source = makeColorSource([[3, 4, 0]]);
    const result = await rangeColorMode.computeColors(
      source,
      makeColorBuffer(source.pointCount),
      NO_ABORT,
    );
    expect(result.legend?.low).toBeCloseTo(5);
  });

  it("reports the legend in metres", async () => {
    const source = makeColorSource([
      [1, 0, 0],
      [2, 0, 0],
    ]);
    const result = await rangeColorMode.computeColors(
      source,
      makeColorBuffer(source.pointCount),
      NO_ABORT,
    );
    expect(result.legend?.unit).toBe("m");
  });

  it("puts near points at the bottom of the ramp and far ones at the top", async () => {
    const source = makeColorSource([
      [1, 0, 0],
      [50, 0, 0],
    ]);
    const colors = await color(rangeColorMode, source);
    const near = new Float32Array(3);
    scalarRamp(0, near, 0);
    expectColorAt(colors, 0, [...near]);
    expect(colorAt(colors, 1)).not.toEqual([...near]);
  });

  it("does not leave a near-field-dominated sweep in the bottom of the ramp", async () => {
    // The reported bug: returns cluster hard at short range (median 6 m against
    // 62 m), so a linear map rendered the street uniformly blue.
    const sweep = skewedCloud((d) => [d, 0, 0, 0]);
    expect(await fractionInBottomQuarter(rangeColorMode, sweep)).toBeLessThan(0.45);
  });
});

// ─── Shared ramp ──────────────────────────────────────────────────────────────

describe("scalarRamp", () => {
  it("writes at the given offset and leaves its neighbours alone", () => {
    const out = new Float32Array(9).fill(-1);
    scalarRamp(0.5, out, 3);
    expect(out[2]).toBe(-1);
    expect(out[6]).toBe(-1);
    expect(out.slice(3, 6).every((c) => c >= 0 && c <= 1)).toBe(true);
  });

  it("clamps out-of-range inputs to the ramp ends", () => {
    const below = new Float32Array(3);
    const atZero = new Float32Array(3);
    const above = new Float32Array(3);
    const atOne = new Float32Array(3);
    scalarRamp(-5, below, 0);
    scalarRamp(0, atZero, 0);
    scalarRamp(5, above, 0);
    scalarRamp(1, atOne, 0);
    expect([...below]).toEqual([...atZero]);
    expect([...above]).toEqual([...atOne]);
  });

  it("treats NaN as the bottom of the ramp rather than propagating it", () => {
    // A NaN component would silently drop the point from the GPU buffer.
    const out = new Float32Array(3);
    scalarRamp(Number.NaN, out, 0);
    expect([...out].some(Number.isNaN)).toBe(false);
  });

  it("varies in lightness across the range, not only in hue", () => {
    // What keeps it readable for a red-green colour-blind viewer.
    const low = new Float32Array(3);
    const mid = new Float32Array(3);
    scalarRamp(0, low, 0);
    scalarRamp(0.75, mid, 0);
    const lightness = (c: Float32Array) => c[0] + c[1] + c[2];
    expect(lightness(mid)).toBeGreaterThan(lightness(low));
  });
});
