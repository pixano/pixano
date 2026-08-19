/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Floats per point in the stored binary: `[x, y, z, intensity, ring]`.
 * The builder writes whatever the source dataset carried past XYZ
 * (`builders/folders/builder_3d.py` hstacks `points[:, 3:]` onto the world
 * coordinates), which for the nuScenes-style lidars is intensity then ring.
 */
export const POINT_STRIDE = 5;

/**
 * Named offsets into one point's stride. These are indices a colour mode
 * passes to `channel()`; they are named here so a mode says `CHANNEL_INTENSITY`
 * rather than `3`, and so a dataset with a different layout has one table to
 * correct instead of a constant scattered across modes.
 */
export const CHANNEL_X = 0;
export const CHANNEL_Y = 1;
export const CHANNEL_Z = 2;
export const CHANNEL_INTENSITY = 3;
export const CHANNEL_RING = 4;

/** Axis-aligned bounding box in Three.js space. */
export interface PointCloudBounds {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  minZ: number;
  maxZ: number;
}

const EMPTY_BOUNDS: PointCloudBounds = {
  minX: 0,
  maxX: 0,
  minY: 0,
  maxY: 0,
  minZ: 0,
  maxZ: 0,
};

export interface ParsedPointCloud {
  pointCount: number;
  /** Three.js XYZ positions, length = pointCount × 3. */
  positions: Float32Array;
  bounds: PointCloudBounds;
  /**
   * One raw stride channel, de-interleaved into a dense array of length
   * `pointCount`. Decoded on first request and memoised, so a colour mode pays
   * for the channel it reads and nothing else — and a mode reading a channel no
   * one read before needs no change here.
   *
   * Out-of-range indices yield a zero-filled array rather than throwing: a
   * cloud whose stride is shorter than this one's is missing data, not
   * corrupt, and a mode's `unavailableReason` is where that gets reported.
   */
  channel(index: number): Float32Array;
}

/**
 * Parses a raw Lance point-cloud binary buffer into Three.js-space positions
 * and a bounding box, keeping the buffer around so any stride channel can be
 * decoded later.
 *
 * Deliberately colour-free: colouring is a per-mode plugin
 * (`pointcloud/coloring/`), and baking one scheme in here is what previously
 * made "colour the cloud differently" a parser change.
 */
export function parsePointCloud(buffer: ArrayBuffer): ParsedPointCloud {
  const floats = new Float32Array(buffer);
  const pointCount = Math.floor(floats.length / POINT_STRIDE);
  const positions = new Float32Array(pointCount * 3);
  const channelCache = new Map<number, Float32Array>();

  const channel = (index: number): Float32Array => {
    const cached = channelCache.get(index);
    if (cached) return cached;
    const values = new Float32Array(pointCount);
    if (index >= 0 && index < POINT_STRIDE) {
      for (let i = 0; i < pointCount; i++) values[i] = floats[i * POINT_STRIDE + index];
    }
    channelCache.set(index, values);
    return values;
  };

  if (pointCount === 0) {
    return { pointCount, positions, bounds: EMPTY_BOUNDS, channel };
  }

  // Apply the Lance→Three.js axis swap (lanceToThree: [lx, lz, -ly]) and
  // accumulate the bounds in the same pass.
  let minX = Infinity,
    maxX = -Infinity;
  let minY = Infinity,
    maxY = -Infinity;
  let minZ = Infinity,
    maxZ = -Infinity;

  for (let i = 0; i < pointCount; i++) {
    const lx = floats[i * POINT_STRIDE + CHANNEL_X];
    const ly = floats[i * POINT_STRIDE + CHANNEL_Y];
    const lz = floats[i * POINT_STRIDE + CHANNEL_Z];

    const tx = lx;
    const ty = lz;
    const tz = -ly;

    positions[i * 3] = tx;
    positions[i * 3 + 1] = ty;
    positions[i * 3 + 2] = tz;

    if (tx < minX) minX = tx;
    if (tx > maxX) maxX = tx;
    if (ty < minY) minY = ty;
    if (ty > maxY) maxY = ty;
    if (tz < minZ) minZ = tz;
    if (tz > maxZ) maxZ = tz;
  }

  return { pointCount, positions, bounds: { minX, maxX, minY, maxY, minZ, maxZ }, channel };
}
