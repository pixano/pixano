/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Circle } from "lucide-svelte";

import type { PointCloudColorMode, PointCloudColorSource } from "../colorMode.js";

/**
 * One flat shade for every point — the cloud as pure geometry.
 *
 * Every other mode paints a measurement onto the points, which is exactly what
 * you do not want when the question is about *shape*: reading a silhouette, or
 * judging whether a 3D box encloses the right returns, is easier when nothing
 * competes with the annotation's own colour.
 *
 * Light rather than white: bright enough to read against the dark viewer
 * background, dim enough that a selected annotation still wins the eye.
 */
const NEUTRAL_R = 0.82;
const NEUTRAL_G = 0.84;
const NEUTRAL_B = 0.88;

export const neutralColorMode: PointCloudColorMode = {
  id: "neutral",
  label: "Neutral",
  icon: Circle,

  computeColors(source: PointCloudColorSource, out: Float32Array) {
    for (let i = 0; i < source.pointCount; i++) {
      out[i * 3] = NEUTRAL_R;
      out[i * 3 + 1] = NEUTRAL_G;
      out[i * 3 + 2] = NEUTRAL_B;
    }
    return {};
  },
};
