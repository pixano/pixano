/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Radius } from "lucide-svelte";

import type { PointCloudColorMode, PointCloudColorSource } from "../colorMode.js";
import { equalize, scalarRamp } from "../colorRamp.js";

/** Row-major 4×4 indices of the rows that produce a transformed XYZ. */
const ROW_X = 0;
const ROW_Y = 4;
const ROW_Z = 8;
const COL_X = 0;
const COL_Y = 1;
const COL_Z = 2;
const COL_TRANSLATION = 3;

/**
 * Distance from each point to the lidar that measured it.
 *
 * A `CalibratedPointCloud` stores its points in **world** coordinates — the
 * builder applies `sensor2world` before writing them — so the sensor is not at
 * the origin and the distance is not the norm of the stored point. Running the
 * world-to-sensor extrinsics over a point puts it back in the sensor frame,
 * where the norm *is* the range.
 *
 * With no extrinsics the transform is the identity, which is the right answer
 * rather than a fallback: a plain `PointCloud` view is stored in the sensor
 * frame already. The case this cannot detect is a calibrated cloud whose matrix
 * failed to load — it would then read distances from the world origin. That
 * shows up as an implausible legend (hundreds of metres), not as a silently
 * plausible one.
 *
 * Ranges are fed to the ramp by rank (`equalize`), because a sweep's returns
 * cluster hard at short range: the nuScenes median is 6 m against a 62 m 99th
 * percentile, so a linear map left most of the street in the bottom quarter of
 * the ramp and the cloud read as uniformly blue.
 */
export const rangeColorMode: PointCloudColorMode = {
  id: "range",
  label: "Distance to sensor",
  icon: Radius,

  computeColors(source: PointCloudColorSource, out: Float32Array) {
    const m = source.worldToSensor;
    const distances = new Float32Array(source.pointCount);
    const lance: [number, number, number] = [0, 0, 0];

    for (let i = 0; i < source.pointCount; i++) {
      source.toLance(i, lance);
      const [x, y, z] = lance;

      let sx = x;
      let sy = y;
      let sz = z;
      if (m) {
        sx =
          m[ROW_X + COL_X] * x +
          m[ROW_X + COL_Y] * y +
          m[ROW_X + COL_Z] * z +
          m[ROW_X + COL_TRANSLATION];
        sy =
          m[ROW_Y + COL_X] * x +
          m[ROW_Y + COL_Y] * y +
          m[ROW_Y + COL_Z] * z +
          m[ROW_Y + COL_TRANSLATION];
        sz =
          m[ROW_Z + COL_X] * x +
          m[ROW_Z + COL_Y] * y +
          m[ROW_Z + COL_Z] * z +
          m[ROW_Z + COL_TRANSLATION];
      }

      distances[i] = Math.hypot(sx, sy, sz);
    }

    const scale = equalize(distances);
    for (let i = 0; i < source.pointCount; i++) {
      scalarRamp(scale.t[i], out, i * 3);
    }

    return {
      legend: { low: scale.low, mid: scale.mid, high: scale.high, unit: "m", ramp: scalarRamp },
    };
  },
};
