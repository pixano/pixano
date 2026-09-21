/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { expect } from "vitest";

import { parsePointCloud, POINT_STRIDE } from "../../pointCloudParser.js";
import type { PixelGrid, PointCloudColorSource, ProjectionCamera } from "../colorMode.js";
import { createColorSource } from "../colorSource.js";
import type { CameraCalibration } from "$lib/annotations/types.js";

/** One point's worth of the stored layout: `[x, y, z, intensity, ring]`. */
export type RawPoint = [number, number, number, number?, number?];

/**
 * A colour source over the given Lance-space points, built through the real
 * parser rather than a hand-written stand-in: the axis swap and the channel
 * de-interleave are exactly the parts a mode's maths depends on, so faking them
 * would let a mode pass its tests and be wrong in the app.
 */
export function makeColorSource(
  points: RawPoint[],
  context: {
    worldToSensor?: readonly number[] | null;
    cameras?: readonly ProjectionCamera[];
  } = {},
): PointCloudColorSource {
  const data = new Float32Array(points.length * POINT_STRIDE);
  for (let i = 0; i < points.length; i++) {
    for (let component = 0; component < POINT_STRIDE; component++) {
      data[i * POINT_STRIDE + component] = points[i][component] ?? 0;
    }
  }
  return createColorSource(parsePointCloud(data.buffer), context);
}

/** A colour buffer sized for `pointCount`, pre-filled so a mode must overwrite it. */
export function makeColorBuffer(pointCount: number, fill = -1): Float32Array {
  return new Float32Array(pointCount * 3).fill(fill);
}

/** The RGB triple written for point `i`. */
export function colorAt(colors: Float32Array, i: number): [number, number, number] {
  return [colors[i * 3], colors[i * 3 + 1], colors[i * 3 + 2]];
}

/**
 * Assert the colour of point `i`, component by component.
 *
 * Not `toEqual` on the triple: the buffer is a `Float32Array`, so 0.4 comes back
 * as 0.4000000059604645 and an exact comparison fails on a correct value. Every
 * colour assertion goes through here so that trap is met once.
 */
export function expectColorAt(colors: Float32Array, i: number, expected: readonly number[]): void {
  const actual = colorAt(colors, i);
  for (let component = 0; component < expected.length; component++) {
    expect(actual[component], `component ${component} of point ${i}`).toBeCloseTo(
      expected[component],
    );
  }
}

export const IDENTITY_MATRIX_4X4: readonly number[] = [
  1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1,
];

/**
 * A world-to-sensor transform for a sensor sitting at `position` with no
 * rotation. World-to-sensor is the *inverse* of the sensor's pose, so the
 * translation is negated — the same convention the builder writes
 * (`t = -R·C`).
 */
export function worldToSensorAt(position: [number, number, number]): readonly number[] {
  return [1, 0, 0, -position[0], 0, 1, 0, -position[1], 0, 0, 1, -position[2], 0, 0, 0, 1];
}

/** A solid-colour pixel grid, as a decoded camera image. */
export function makePixelGrid(
  width: number,
  height: number,
  rgb: [number, number, number],
): PixelGrid {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < width * height; i++) {
    data[i * 4] = rgb[0];
    data[i * 4 + 1] = rgb[1];
    data[i * 4 + 2] = rgb[2];
    data[i * 4 + 3] = 255;
  }
  return { width, height, data };
}

export interface FakeCameraOptions {
  id?: string;
  name?: string;
  imageWidth?: number;
  imageHeight?: number;
  /** World-to-camera 4×4; defaults to the identity (camera at the world origin). */
  extrinsicMatrix?: readonly number[];
  focal?: [number, number];
  principalPoint?: [number, number];
  /** Pixels to serve, or null to simulate an image that could not be read. */
  pixels?: PixelGrid | null;
}

/**
 * A `ProjectionCamera` with no DOM behind it — the reason `loadPixels` is a port
 * on the interface rather than a method that reaches for an `<img>`.
 */
export function makeCamera(options: FakeCameraOptions = {}): ProjectionCamera & {
  loadCount: () => number;
} {
  const imageWidth = options.imageWidth ?? 4;
  const imageHeight = options.imageHeight ?? 4;
  const pixels =
    options.pixels === undefined
      ? makePixelGrid(imageWidth, imageHeight, [255, 0, 0])
      : options.pixels;
  const calibration: CameraCalibration = {
    f: options.focal ?? [1, 1],
    c: options.principalPoint ?? [imageWidth / 2, imageHeight / 2],
    distortion: [],
    extrinsicMatrix: [...(options.extrinsicMatrix ?? IDENTITY_MATRIX_4X4)],
    egoToWorld: [...IDENTITY_MATRIX_4X4],
  };
  let loads = 0;

  return {
    id: options.id ?? "cam",
    name: options.name ?? "CAM_FRONT",
    imageWidth,
    imageHeight,
    calibration,
    loadPixels: () => {
      loads++;
      return Promise.resolve(pixels);
    },
    loadCount: () => loads,
  };
}
