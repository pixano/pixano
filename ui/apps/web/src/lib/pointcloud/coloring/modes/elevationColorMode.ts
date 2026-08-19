/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Mountain } from "lucide-svelte";

import type { PointCloudColorMode, PointCloudColorSource } from "../colorMode.js";
import { equalize, scalarRamp } from "../colorRamp.js";

/** Three.js Y is the up axis (the parser maps Lance Z onto it). */
const AXIS_COMPONENT_UP = 1;

/**
 * Colours by height above the cloud's lowest return.
 *
 * Heights are fed to the ramp by rank rather than by value. A street sweep is
 * overwhelmingly ground: on a nuScenes record 97% of returns sit below the
 * midpoint of the raw min-max span, because a handful of returns off a building
 * stretch the top of the range. Mapping linearly gave every one of those ground
 * points the bottom of the ramp, so the cloud rendered as one flat blue sheet —
 * "no colouring at all" from the user's side. Equalising spreads the road
 * surface, the kerbs and the vehicles apart, which is the structure this mode
 * exists to show.
 *
 * The legend is relative to the lowest point, not the dataset's world Z: an
 * absolute world altitude is an arbitrary number to a reader, while "1.6 m above
 * the ground" is the height of a car roof.
 */
export const elevationColorMode: PointCloudColorMode = {
  id: "elevation",
  label: "Elevation",
  icon: Mountain,

  computeColors(source: PointCloudColorSource, out: Float32Array) {
    const floor = source.bounds.minY;
    const heights = new Float32Array(source.pointCount);
    for (let i = 0; i < source.pointCount; i++) {
      heights[i] = source.positions[i * 3 + AXIS_COMPONENT_UP] - floor;
    }

    const scale = equalize(heights);
    for (let i = 0; i < source.pointCount; i++) {
      scalarRamp(scale.t[i], out, i * 3);
    }

    return {
      legend: { low: scale.low, mid: scale.mid, high: scale.high, unit: "m", ramp: scalarRamp },
    };
  },
};
