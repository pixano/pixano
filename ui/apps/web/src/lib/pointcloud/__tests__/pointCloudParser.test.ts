/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  CHANNEL_INTENSITY,
  CHANNEL_RING,
  parsePointCloud,
  POINT_STRIDE,
} from "../pointCloudParser.js";

/** One point's worth of the stored layout: `[x, y, z, intensity, ring]`. */
type RawPoint = [number, number, number, number?, number?];

function buildBuffer(points: RawPoint[]): ArrayBuffer {
  const data = new Float32Array(points.length * POINT_STRIDE);
  for (let i = 0; i < points.length; i++) {
    for (let component = 0; component < POINT_STRIDE; component++) {
      data[i * POINT_STRIDE + component] = points[i][component] ?? 0;
    }
  }
  return data.buffer;
}

// ─── Empty buffer ─────────────────────────────────────────────────────────────

describe("parsePointCloud — empty buffer", () => {
  it("reports no points and an empty position array", () => {
    const { pointCount, positions } = parsePointCloud(new ArrayBuffer(0));
    expect(pointCount).toBe(0);
    expect(positions.length).toBe(0);
  });

  it("returns zero bounds", () => {
    const { bounds } = parsePointCloud(new ArrayBuffer(0));
    expect(bounds).toEqual({ minX: 0, maxX: 0, minY: 0, maxY: 0, minZ: 0, maxZ: 0 });
  });

  it("still answers channel requests, with an empty array", () => {
    // A colour mode reads its channel before checking the count; it must not
    // have to guard against undefined.
    expect(parsePointCloud(new ArrayBuffer(0)).channel(CHANNEL_INTENSITY).length).toBe(0);
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

  it("counts whole points only, ignoring a truncated trailing record", () => {
    const partial = new Float32Array(POINT_STRIDE + 2);
    expect(parsePointCloud(partial.buffer).pointCount).toBe(1);
  });
});

// ─── Raw channels ─────────────────────────────────────────────────────────────

describe("parsePointCloud — raw channels", () => {
  it("de-interleaves the intensity channel", () => {
    const { channel } = parsePointCloud(
      buildBuffer([
        [0, 0, 0, 12],
        [1, 1, 1, 34],
      ]),
    );
    expect([...channel(CHANNEL_INTENSITY)]).toEqual([12, 34]);
  });

  it("de-interleaves the ring channel", () => {
    // The channel no colour mode reads yet: the point of a generic accessor is
    // that reaching for it later needs no parser change.
    const { channel } = parsePointCloud(
      buildBuffer([
        [0, 0, 0, 0, 7],
        [0, 0, 0, 0, 9],
      ]),
    );
    expect([...channel(CHANNEL_RING)]).toEqual([7, 9]);
  });

  it("returns the same array instance on a second request", () => {
    // Memoised: two modes reading intensity must not each pay the de-interleave.
    const { channel } = parsePointCloud(buildBuffer([[0, 0, 0, 5]]));
    expect(channel(CHANNEL_INTENSITY)).toBe(channel(CHANNEL_INTENSITY));
  });

  it("yields zeros for a channel beyond the stride", () => {
    const { channel } = parsePointCloud(buildBuffer([[1, 2, 3, 4, 5]]));
    expect([...channel(POINT_STRIDE)]).toEqual([0]);
  });

  it("does not colour the cloud", () => {
    // Colouring is a plugin (`coloring/`); a parser that baked one scheme in is
    // what made "colour the cloud differently" a parser change.
    expect("colors" in parsePointCloud(buildBuffer([[0, 0, 0]]))).toBe(false);
  });
});

// ─── Bounding box ─────────────────────────────────────────────────────────────

describe("parsePointCloud — Three.js bounding box", () => {
  it("computes the correct bounds from two opposite points", () => {
    // Lance (-1,-2,-3) → Three.js (-1,-3, 2)
    // Lance ( 1, 2, 3) → Three.js ( 1, 3,-2)
    const { bounds } = parsePointCloud(
      buildBuffer([
        [-1, -2, -3],
        [1, 2, 3],
      ]),
    );
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
