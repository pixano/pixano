/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Signal } from "lucide-svelte";

import { CHANNEL_INTENSITY } from "../../pointCloudParser.js";
import type { PointCloudColorMode, PointCloudColorSource } from "../colorMode.js";
import { equalize, scalarRamp } from "../colorRamp.js";

/**
 * Colours by return strength — the lidar's per-point intensity channel.
 *
 * Reads how reflective each surface is at the laser's wavelength, which is what
 * makes lane markings, licence plates and road signs stand out against asphalt
 * that is geometrically identical to them.
 *
 * The channel is strongly skewed (a nuScenes sweep has a median of 11 against a
 * 99th percentile of 100), so the ramp is fed by rank rather than by value —
 * see `equalize`. A linear map put four points in five into the bottom quarter
 * of the ramp and rendered the whole cloud blue.
 */
export const intensityColorMode: PointCloudColorMode = {
  id: "intensity",
  label: "Intensity",
  icon: Signal,

  unavailableReason(source: PointCloudColorSource) {
    if (source.pointCount === 0) return null;
    const intensity = source.channel(CHANNEL_INTENSITY);
    // A cloud whose intensity column is uniformly zero carries no measurement:
    // the importer padded the stride, or the sensor never recorded one. Better
    // to say so than to hand back a flat cloud that looks like a bug.
    for (let i = 0; i < intensity.length; i++) {
      if (intensity[i] !== 0) return null;
    }
    return "This point cloud records no intensity";
  },

  computeColors(source: PointCloudColorSource, out: Float32Array) {
    const scale = equalize(source.channel(CHANNEL_INTENSITY));
    for (let i = 0; i < source.pointCount; i++) {
      scalarRamp(scale.t[i], out, i * 3);
    }

    // Unitless on purpose: intensity is uncalibrated and scaled differently by
    // every sensor, so the numbers are only comparable within one cloud.
    return { legend: { low: scale.low, mid: scale.mid, high: scale.high, ramp: scalarRamp } };
  },
};
