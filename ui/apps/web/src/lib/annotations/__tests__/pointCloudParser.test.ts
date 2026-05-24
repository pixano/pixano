/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { parsePointCloud } from "../pointCloudParser";

// Build a raw binary buffer from an array of Lance [x, y, z] points.
// The format is 5 floats per point: [x, y, z, intensity(=0), unused(=0)].
function buildBuffer(points: [number, number, number][]): ArrayBuffer {
  const data = new Float32Array(points.length * 5);
  for (let i = 0; i < points.length; i++) {
    data[i * 5] = points[i][0];
    data[i * 5 + 1] = points[i][1];
    data[i * 5 + 2] = points[i][2];
  }
  return data.buffer;
}

// ─── Empty buffer ─────────────────────────────────────────────────────────────

describe("parsePointCloud — empty buffer", () => {
  it("returns empty position and color arrays", () => {
    const { positions, colors } = parsePointCloud(new ArrayBuffer(0));
    expect(positions.length).toBe(0);
    expect(colors.length).toBe(0);
  });

  it("returns zero bounds", () => {
    const { bounds } = parsePointCloud(new ArrayBuffer(0));
    expect(bounds).toEqual({ minX: 0, maxX: 0, minY: 0, maxY: 0, minZ: 0, maxZ: 0 });
  });
});

// ─── Coordinate transform ─────────────────────────────────────────────────────

describe("parsePointCloud — Lance→Three.js coordinate transform", () => {
  it("maps [lx, ly, lz] to Three.js [lx, lz, -ly]", () => {
    const { positions } = parsePointCloud(buildBuffer([[1, 2, 3]]));
    expect(positions[0]).toBeCloseTo(1); // Three.js X = Lance X
    expect(positions[1]).toBeCloseTo(3); // Three.js Y = Lance Z
    expect(positions[2]).toBeCloseTo(-2); // Three.js Z = -Lance Y
  });

  it("handles negative coordinates", () => {
    const { positions } = parsePointCloud(buildBuffer([[-1, -2, -3]]));
    expect(positions[0]).toBeCloseTo(-1);
    expect(positions[1]).toBeCloseTo(-3);
    expect(positions[2]).toBeCloseTo(2);
  });
});

// ─── Elevation colors ─────────────────────────────────────────────────────────

describe("parsePointCloud — elevation colors", () => {
  it("assigns R=0 to the lowest Lance Z point", () => {
    // Point A at Lance Z=0 (minimum elevation): t=0, R=0
    const { colors } = parsePointCloud(buildBuffer([[0, 0, 0], [0, 0, 10]]));
    expect(colors[0]).toBeCloseTo(0); // R of point A
  });

  it("assigns R=1 to the highest Lance Z point", () => {
    // Point B at Lance Z=10 (maximum elevation): t=1, R=1
    const { colors } = parsePointCloud(buildBuffer([[0, 0, 0], [0, 0, 10]]));
    expect(colors[3]).toBeCloseTo(1); // R of point B
  });

  it("assigns stable colors when all points share the same elevation", () => {
    // Single elevation: lanceZRange falls back to 1, t=0 for all points
    const { colors } = parsePointCloud(buildBuffer([[0, 0, 5], [1, 0, 5]]));
    expect(colors[0]).toBeCloseTo(0); // R: t=0
    expect(colors[1]).toBeCloseTo(0.4); // G: GREEN_MIN + 0 * GREEN_RANGE = 0.4
    expect(colors[2]).toBeCloseTo(1.0); // B: 1 - 0 * BLUE_DECAY = 1
  });

  it("colors are interpolated for a mid-elevation point", () => {
    // Three points: Z=0, Z=5, Z=10 → t=0, 0.5, 1
    const { colors } = parsePointCloud(buildBuffer([[0, 0, 0], [0, 0, 5], [0, 0, 10]]));
    expect(colors[3]).toBeCloseTo(0.5); // R of mid point
    expect(colors[4]).toBeCloseTo(0.4 + 0.5 * 0.4); // G
    expect(colors[5]).toBeCloseTo(1 - 0.5 * 0.5); // B
  });
});

// ─── Bounding box ─────────────────────────────────────────────────────────────

describe("parsePointCloud — Three.js bounding box", () => {
  it("computes the correct bounds from two opposite points", () => {
    // Lance (-1,-2,-3) → Three.js (-1,-3, 2)
    // Lance ( 1, 2, 3) → Three.js ( 1, 3,-2)
    const { bounds } = parsePointCloud(buildBuffer([[-1, -2, -3], [1, 2, 3]]));
    expect(bounds.minX).toBeCloseTo(-1);
    expect(bounds.maxX).toBeCloseTo(1);
    expect(bounds.minY).toBeCloseTo(-3);
    expect(bounds.maxY).toBeCloseTo(3);
    expect(bounds.minZ).toBeCloseTo(-2);
    expect(bounds.maxZ).toBeCloseTo(2);
  });

  it("returns degenerate bounds for a single point", () => {
    const { bounds } = parsePointCloud(buildBuffer([[2, 4, 6]]));
    // Three.js: [2, 6, -4]
    expect(bounds.minX).toBeCloseTo(2);
    expect(bounds.maxX).toBeCloseTo(2);
    expect(bounds.minY).toBeCloseTo(6);
    expect(bounds.maxY).toBeCloseTo(6);
    expect(bounds.minZ).toBeCloseTo(-4);
    expect(bounds.maxZ).toBeCloseTo(-4);
  });
});
