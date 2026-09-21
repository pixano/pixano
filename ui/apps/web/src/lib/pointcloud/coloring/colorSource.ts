/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ParsedPointCloud } from "../pointCloudParser.js";
import type { PointCloudColorSource, ProjectionCamera } from "./colorMode.js";

/** The record-level context the parser cannot know, supplied by the widget. */
export interface ColorSourceContext {
  /** World-to-sensor 4×4 of the lidar; null for an uncalibrated cloud. */
  worldToSensor?: readonly number[] | null;
  cameras?: readonly ProjectionCamera[];
}

/**
 * Joins a parsed cloud with its record context into the read-only surface
 * colour modes program against.
 *
 * Thin on purpose: everything expensive stays lazy in the parser's `channel`,
 * so building a source costs nothing and the widget can rebuild one whenever
 * the cameras resolve without re-parsing the cloud.
 */
export function createColorSource(
  parsed: ParsedPointCloud,
  context: ColorSourceContext = {},
): PointCloudColorSource {
  return {
    pointCount: parsed.pointCount,
    positions: parsed.positions,
    bounds: parsed.bounds,
    channel: (index) => parsed.channel(index),
    // Inverse of the parser's Lance→Three swap (`[lx, lz, -ly]`): the Lance Y
    // axis is the negated Three Z, and Lance Z is Three Y.
    toLance: (i, out) => {
      out[0] = parsed.positions[i * 3];
      out[1] = -parsed.positions[i * 3 + 2];
      out[2] = parsed.positions[i * 3 + 1];
    },
    worldToSensor: context.worldToSensor ?? null,
    cameras: context.cameras ?? [],
  };
}
