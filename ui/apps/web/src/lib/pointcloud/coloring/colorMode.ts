/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { IconProps } from "lucide-svelte";
import type { Component, ComponentType, SvelteComponent } from "svelte";

import type { PointCloudBounds } from "../pointCloudParser.js";
import type { ColorRamp } from "./colorRamp.js";
import type { CameraCalibration } from "$lib/annotations/types.js";

/** RGBA pixels of a decoded image, as `getImageData` hands them over. */
export interface PixelGrid {
  width: number;
  height: number;
  /** Row-major RGBA, 4 bytes per pixel. */
  data: Uint8ClampedArray;
}

/**
 * One calibrated camera that observed the same record as the cloud.
 *
 * `loadPixels` is a port, not a method that reads the DOM: the widget supplies
 * an implementation backed by an `<img>` and a canvas, and tests supply a plain
 * object. That keeps colour modes free of DOM access and unit-testable without
 * a real image decoder.
 */
export interface ProjectionCamera {
  id: string;
  /** Logical view name, e.g. "CAM_FRONT" — used in messages, not for lookups. */
  name: string;
  imageWidth: number;
  imageHeight: number;
  /** Intrinsics plus the world-to-camera extrinsics. */
  calibration: CameraCalibration;
  /** Decoded pixels, or null when the image could not be read. */
  loadPixels(signal: AbortSignal): Promise<PixelGrid | null>;
}

/**
 * Everything a colour mode may read about the cloud it is colouring.
 *
 * The accessors are deliberately **generic rather than one field per mode**.
 * `channel(index)` is the important one: it is the same lesson as
 * `listAnnotations(resource)` replacing `listBBoxes`/`listBBox3Ds` in the
 * annotation gateway — a named field per consumer means every new consumer
 * widens the interface, and the plugin seam stops holding at the first mode
 * that wants something unforeseen. A mode reading intensity, ring index, or
 * any future stride channel needs no change to this type.
 *
 * What this contract does *not* cover: data the widget does not have at all
 * (per-point semantic labels from another table, a second cloud to diff
 * against). Those need real plumbing — a gateway call and a seed field — and no
 * accessor shape can pretend otherwise.
 */
export interface PointCloudColorSource {
  readonly pointCount: number;
  /** Three.js-space XYZ, length = pointCount × 3. */
  readonly positions: Float32Array;
  readonly bounds: PointCloudBounds;
  /** A raw stride channel, dense and memoised. See `ParsedPointCloud.channel`. */
  channel(index: number): Float32Array;
  /**
   * Point `i` in Lance/world space, written into `out`. This is the frame the
   * calibration matrices are expressed in, so any mode doing geometry against
   * a sensor or a camera goes through here rather than re-deriving the axis
   * swap. Writes into the caller's tuple so a per-point loop allocates nothing.
   */
  toLance(i: number, out: [number, number, number]): void;
  /**
   * World-to-sensor 4×4 (row-major) of the lidar that produced the cloud, or
   * null when the view is an uncalibrated `PointCloud`. Null is meaningful
   * rather than missing: those clouds are stored in the sensor frame already,
   * so the identity is the correct transform for them.
   */
  readonly worldToSensor: readonly number[] | null;
  /** Calibrated cameras of the same record, in the dataset's declared order. */
  readonly cameras: readonly ProjectionCamera[];
}

/**
 * What a mode reports back about the colouring it just produced. Optional
 * throughout: a mode that has nothing to add returns an empty object.
 */
export interface PointCloudColoring {
  /**
   * The scale the colours encode, when they encode one. Modes that map a
   * continuous quantity (intensity, range) are unreadable without it — and
   * having it in the contract from the start is what keeps adding a legend
   * later from touching every mode.
   */
  legend?: {
    /** Value at the bottom of the ramp. */
    low: number;
    /**
     * Value at the ramp's midpoint. Not decoration: the scalar modes map by
     * rank, so the middle colour marks the median rather than the arithmetic
     * mean of the bounds. Showing it is what keeps the legend from implying a
     * linearity the mapping does not have.
     */
    mid: number;
    /** Value at the top of the ramp. */
    high: number;
    /** Unit shown next to the values, e.g. "m". Omitted when unitless. */
    unit?: string;
    ramp: ColorRamp;
  };
  /**
   * Points the mode could not colour and left at the fallback shade, e.g.
   * points no camera sees. Surfaced to the user so an oddly grey cloud is
   * explained rather than looking like a bug.
   */
  uncoloredCount?: number;
}

/** Props a mode's optional own controls receive from the menu. */
export interface ColorModeControlsProps {
  /** Ask for a recompute after the control changed the mode's settings. */
  requestRecolor: () => void;
}

/**
 * A point-cloud colouring plugin.
 *
 * Adding one means: a module under `coloring/modes/` exporting one of these,
 * plus a line in `COLOR_MODES_3D`. No parser, scene, widget, menu or sibling
 * mode changes — `colorModes.test.ts` is what keeps that true.
 */
export interface PointCloudColorMode {
  /** Stable id; persisted in widget storage, so renaming one resets the user's choice. */
  id: string;
  /** Menu entry text. */
  label: string;
  icon: ComponentType<SvelteComponent<IconProps>>;
  /**
   * Why this mode cannot run on this cloud, or null when it can. The menu keeps
   * the entry visible and disabled with this as its tooltip: a mode that
   * silently vanishes reads as a missing feature, while one that explains
   * itself ("no calibrated camera in this record") teaches the data model.
   */
  unavailableReason?(source: PointCloudColorSource): string | null;
  /**
   * Write `pointCount × 3` RGB components in [0, 1] into `out`.
   *
   * `out` is reused across mode switches, so a mode must fill every point it
   * claims rather than assume a cleared buffer. Async because a mode may need
   * to fetch and decode images; long ones must honour `signal`, which is
   * aborted when the user switches mode or the record changes.
   */
  computeColors(
    source: PointCloudColorSource,
    out: Float32Array,
    signal: AbortSignal,
  ): PointCloudColoring | Promise<PointCloudColoring>;
  /**
   * Optional controls the mode owns (clamp bounds, ramp choice…), mounted by
   * the menu underneath the entry. Same arrangement as `Tool3D.hud`: the host
   * mounts it and knows nothing about it, so a mode gaining a setting never
   * turns the menu into a place every mode has to edit.
   */
  controls?: Component<ColorModeControlsProps>;
}
