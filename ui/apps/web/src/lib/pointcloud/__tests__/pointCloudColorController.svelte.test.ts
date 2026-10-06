/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { makePixelGrid } from "../coloring/__tests__/fakeColorSource.js";
import type { PixelGrid, ProjectionCamera } from "../coloring/colorMode.js";
import { cameraProjectionColorMode } from "../coloring/modes/cameraProjectionColorMode.js";
import { elevationColorMode } from "../coloring/modes/elevationColorMode.js";
import { DEFAULT_COLOR_MODE_ID } from "../coloring/registry.js";
import { PointCloudColorController } from "../pointCloudColorController.svelte.js";
import { parsePointCloud, POINT_STRIDE } from "../pointCloudParser.js";

const BYTE_MAX = 255;

/** World-to-camera permutation putting Lance +X on the camera's viewing axis. */
const LOOKING_DOWN_WORLD_X: readonly number[] = [0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1];

function makeCloud(points: [number, number, number][]) {
  const data = new Float32Array(points.length * POINT_STRIDE);
  for (let i = 0; i < points.length; i++) {
    data[i * POINT_STRIDE] = points[i][0];
    data[i * POINT_STRIDE + 1] = points[i][1];
    data[i * POINT_STRIDE + 2] = points[i][2];
    // Intensity *decreasing* while height increases, so height-ranked and
    // intensity-ranked colourings disagree — otherwise the two modes would
    // produce identical buffers on a fixture this small and "the mode switch
    // actually recoloured" could not be observed.
    data[i * POINT_STRIDE + 3] = points.length - i;
  }
  return parsePointCloud(data.buffer);
}

/**
 * A camera whose pixels arrive only when the test says so. The real projection
 * mode is driven throughout — the point is to exercise the controller's
 * cancellation against a genuinely slow mode, not against a stub of one.
 */
function makeDeferredCamera(pixels: PixelGrid | null = makePixelGrid(4, 4, [BYTE_MAX, 0, 0])): {
  camera: ProjectionCamera;
  resolve: () => void;
  reject: (reason: Error) => void;
} {
  let resolve!: () => void;
  let reject!: (reason: Error) => void;
  const gate = new Promise<void>((res, rej) => {
    resolve = () => res();
    reject = rej;
  });

  return {
    camera: {
      id: "cam",
      name: "CAM_FRONT",
      imageWidth: 4,
      imageHeight: 4,
      calibration: {
        f: [1, 1],
        c: [2, 2],
        distortion: [],
        extrinsicMatrix: [...LOOKING_DOWN_WORLD_X],
        egoToWorld: [...LOOKING_DOWN_WORLD_X],
      },
      loadPixels: () => gate.then(() => pixels),
    },
    resolve,
    reject,
  };
}

const POINTS: [number, number, number][] = [
  [5, 0, 0],
  [6, 0, 1],
];

describe("PointCloudColorController", () => {
  it("has no source before a cloud arrives", () => {
    const controller = new PointCloudColorController([], null);
    expect(controller.source).toBeNull();
  });

  it("sizes the colour buffer to the cloud and colours it", async () => {
    const controller = new PointCloudColorController([], null);
    await controller.setMode(DEFAULT_COLOR_MODE_ID);
    await controller.setCloud(makeCloud(POINTS));

    expect(controller.colors.length).toBe(POINTS.length * 3);
    expect(controller.revision).toBeGreaterThan(0);
    expect([...controller.colors].some(Number.isNaN)).toBe(false);
  });

  it("switching mode recolours the same buffer in place", async () => {
    // The renderer holds a `BufferAttribute` over this array; replacing it would
    // leave the GPU reading a detached buffer, which is why `revision` exists
    // as the change signal instead of the array's identity.
    const controller = new PointCloudColorController([], null);
    await controller.setCloud(makeCloud(POINTS));
    const buffer = controller.colors;
    const before = [...buffer];

    await controller.setMode("intensity");

    expect(controller.colors).toBe(buffer);
    expect([...controller.colors]).not.toEqual(before);
  });

  it("bumps the revision on every recolour", async () => {
    const controller = new PointCloudColorController([], null);
    await controller.setCloud(makeCloud(POINTS));
    const afterLoad = controller.revision;

    await controller.setMode("intensity");
    await controller.recolor();

    expect(controller.revision).toBe(afterLoad + 2);
  });

  it("falls back to the default when the stored mode cannot run on this cloud", async () => {
    // A widget restored with the projection mode, then pointed at a record with
    // no camera: the cloud must still be coloured.
    const controller = new PointCloudColorController([], null);
    await controller.setCloud(makeCloud(POINTS));

    await controller.setMode(cameraProjectionColorMode.id);

    expect(controller.activeModeId).toBe(DEFAULT_COLOR_MODE_ID);
    expect([...controller.colors].every((c) => c >= 0)).toBe(true);
  });

  it("falls back for an id no longer in the registry", async () => {
    const controller = new PointCloudColorController([], null);
    await controller.setCloud(makeCloud(POINTS));

    await controller.setMode("a-mode-from-a-previous-release");

    expect(controller.activeModeId).toBe(DEFAULT_COLOR_MODE_ID);
  });

  it("reports that it is still working while an async mode runs", async () => {
    const { camera, resolve } = makeDeferredCamera();
    const controller = new PointCloudColorController([camera], null);
    await controller.setCloud(makeCloud(POINTS));

    const pending = controller.setMode(cameraProjectionColorMode.id);
    expect(controller.recoloring).toBe(true);

    resolve();
    await pending;
    expect(controller.recoloring).toBe(false);
  });

  it("discards a slow pass that a newer mode switch has replaced", async () => {
    // The stale-write hazard: the projection is mid-decode when the user picks
    // elevation. If the older pass published on completion, the cloud would
    // silently flip back to camera colours seconds after the switch.
    const { camera, resolve } = makeDeferredCamera();
    const controller = new PointCloudColorController([camera], null);
    await controller.setCloud(makeCloud(POINTS));

    const slow = controller.setMode(cameraProjectionColorMode.id);
    await controller.setMode(elevationColorMode.id);
    const afterSwitch = [...controller.colors];
    const revisionAfterSwitch = controller.revision;

    resolve();
    await slow;

    expect(controller.activeModeId).toBe(elevationColorMode.id);
    expect([...controller.colors]).toEqual(afterSwitch);
    expect(controller.revision).toBe(revisionAfterSwitch);
  });

  it("keeps the previous colours and reports a failing mode", async () => {
    const { camera, reject } = makeDeferredCamera();
    const controller = new PointCloudColorController([camera], null);
    await controller.setCloud(makeCloud(POINTS));
    const before = [...controller.colors];

    const failing = controller.setMode(cameraProjectionColorMode.id);
    reject(new Error("decode exploded"));
    await failing;

    expect(controller.error).toBe("decode exploded");
    expect(controller.recoloring).toBe(false);
    // A failed recolour must not blank the cloud.
    expect([...controller.colors]).toEqual(before);
  });

  it("clears a previous error on the next successful recolour", async () => {
    const { camera, reject } = makeDeferredCamera();
    const controller = new PointCloudColorController([camera], null);
    await controller.setCloud(makeCloud(POINTS));

    const failing = controller.setMode(cameraProjectionColorMode.id);
    reject(new Error("decode exploded"));
    await failing;
    await controller.setMode("intensity");

    expect(controller.error).toBeNull();
  });

  it("publishes what the mode reported", async () => {
    const controller = new PointCloudColorController([], null);
    await controller.setCloud(makeCloud(POINTS));

    await controller.setMode("intensity");

    // Intensity carries a legend; the widget renders it from here.
    expect(controller.coloring?.legend).toBeDefined();
  });

  it("stops an in-flight pass when disposed", async () => {
    const { camera, resolve } = makeDeferredCamera();
    const controller = new PointCloudColorController([camera], null);
    await controller.setCloud(makeCloud(POINTS));

    const pending = controller.setMode(cameraProjectionColorMode.id);
    const revisionBeforeDispose = controller.revision;
    controller.dispose();

    resolve();
    await pending;

    // The widget is gone; nothing may be published into its buffer.
    expect(controller.revision).toBe(revisionBeforeDispose);
  });

  it("colours an empty cloud without failing", async () => {
    const controller = new PointCloudColorController([], null);
    await controller.setCloud(makeCloud([]));

    expect(controller.colors.length).toBe(0);
    expect(controller.error).toBeNull();
  });
});
