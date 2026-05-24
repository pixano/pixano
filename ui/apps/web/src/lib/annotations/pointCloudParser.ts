/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Binary format: [X, Y, Z, intensity, unused] — only XYZ (indices 0–2) are used.
const POINT_STRIDE = 5;

// Elevation colorization: hue shifts from blue (low) to red (high) with a
// fixed green channel to keep points visible against dark backgrounds.
const ELEVATION_COLOR_GREEN_MIN = 0.4;
const ELEVATION_COLOR_GREEN_RANGE = 0.4;
const ELEVATION_COLOR_BLUE_DECAY = 0.5;

export interface ParsedPointCloud {
  /** Three.js XYZ positions, length = pointCount × 3. */
  positions: Float32Array;
  /** RGB colors in [0, 1] derived from elevation, length = pointCount × 3. */
  colors: Float32Array;
  /** Axis-aligned bounding box in Three.js space. */
  bounds: {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
    minZ: number;
    maxZ: number;
  };
}

/**
 * Parses a raw Lance point-cloud binary buffer into Three.js-space positions,
 * elevation-based colors, and a bounding box — ready for WebGL upload.
 *
 * Two-pass algorithm:
 *   Pass 1 — find the Lance Z range needed for elevation colorization.
 *   Pass 2 — apply the Lance→Three.js axis swap, assign colors, track bounds.
 */
export function parsePointCloud(buffer: ArrayBuffer): ParsedPointCloud {
  const floats = new Float32Array(buffer);
  const pointCount = Math.floor(floats.length / POINT_STRIDE);

  const positions = new Float32Array(pointCount * 3);
  const colors = new Float32Array(pointCount * 3);

  if (pointCount === 0) {
    return {
      positions,
      colors,
      bounds: { minX: 0, maxX: 0, minY: 0, maxY: 0, minZ: 0, maxZ: 0 },
    };
  }

  // Pass 1: determine Lance Z range for elevation normalization.
  let minLanceZ = Infinity;
  let maxLanceZ = -Infinity;
  for (let i = 0; i < pointCount; i++) {
    const lz = floats[i * POINT_STRIDE + 2];
    if (lz < minLanceZ) minLanceZ = lz;
    if (lz > maxLanceZ) maxLanceZ = lz;
  }
  const lanceZRange = maxLanceZ - minLanceZ || 1;

  // Pass 2: transform coordinates (lanceToThree: [lx, lz, -ly]),
  //         assign elevation colors, and accumulate Three.js bounds.
  let minX = Infinity,
    maxX = -Infinity;
  let minY = Infinity,
    maxY = -Infinity;
  let minZ = Infinity,
    maxZ = -Infinity;

  for (let i = 0; i < pointCount; i++) {
    const lx = floats[i * POINT_STRIDE];
    const ly = floats[i * POINT_STRIDE + 1];
    const lz = floats[i * POINT_STRIDE + 2];

    const tx = lx;
    const ty = lz;
    const tz = -ly;

    positions[i * 3] = tx;
    positions[i * 3 + 1] = ty;
    positions[i * 3 + 2] = tz;

    const t = (lz - minLanceZ) / lanceZRange;
    colors[i * 3] = t;
    colors[i * 3 + 1] = ELEVATION_COLOR_GREEN_MIN + t * ELEVATION_COLOR_GREEN_RANGE;
    colors[i * 3 + 2] = 1 - t * ELEVATION_COLOR_BLUE_DECAY;

    if (tx < minX) minX = tx;
    if (tx > maxX) maxX = tx;
    if (ty < minY) minY = ty;
    if (ty > maxY) maxY = ty;
    if (tz < minZ) minZ = tz;
    if (tz > maxZ) maxZ = tz;
  }

  return { positions, colors, bounds: { minX, maxX, minY, maxY, minZ, maxZ } };
}
