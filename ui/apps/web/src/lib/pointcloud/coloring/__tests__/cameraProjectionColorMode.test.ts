/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { UNCOLORED_B, UNCOLORED_G, UNCOLORED_R } from "../colorRamp.js";
import { cameraProjectionColorMode } from "../modes/cameraProjectionColorMode.js";
import {
  expectColorAt,
  makeCamera,
  makeColorBuffer,
  makeColorSource,
  makePixelGrid,
} from "./fakeColorSource.js";

const NO_ABORT = new AbortController().signal;
const BYTE_MAX = 255;

/**
 * A camera looking down Lance +X, which is what these fixtures place points
 * along. World-to-camera has to rotate that axis onto the camera's +Z (its
 * viewing direction), so the matrix is a permutation, not the identity: with the
 * identity, every point along +X sits at camera Z = 0 and nothing projects.
 *
 * Rows map camera (x, y, z) ← world (x, y, z):
 *   cam x = world y, cam y = world z, cam z = world x
 */
const LOOKING_DOWN_WORLD_X: readonly number[] = [0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1];

const RED: [number, number, number] = [BYTE_MAX, 0, 0];
const BLUE: [number, number, number] = [0, 0, BYTE_MAX];

async function projectionOf(
  source: ReturnType<typeof makeColorSource>,
): Promise<{ colors: Float32Array; uncoloredCount?: number }> {
  const colors = makeColorBuffer(source.pointCount);
  const result = await cameraProjectionColorMode.computeColors(source, colors, NO_ABORT);
  return { colors, uncoloredCount: result.uncoloredCount };
}

describe("cameraProjectionColorMode — availability", () => {
  it("is unavailable with no camera in the record", () => {
    expect(cameraProjectionColorMode.unavailableReason?.(makeColorSource([[1, 0, 0]]))).toMatch(
      /no calibrated camera/i,
    );
  });

  it("is available as soon as one camera is calibrated", () => {
    const source = makeColorSource([[1, 0, 0]], { cameras: [makeCamera()] });
    expect(cameraProjectionColorMode.unavailableReason?.(source)).toBeNull();
  });
});

describe("cameraProjectionColorMode — sampling", () => {
  it("paints a visible point with the pixel it lands on", async () => {
    const source = makeColorSource([[5, 0, 0]], {
      cameras: [
        makeCamera({ extrinsicMatrix: LOOKING_DOWN_WORLD_X, pixels: makePixelGrid(4, 4, RED) }),
      ],
    });
    const { colors } = await projectionOf(source);
    expectColorAt(colors, 0, [1, 0, 0]);
  });

  it("leaves a point behind the camera at the fallback shade", async () => {
    // Negative camera Z: the pinhole model would happily produce a pixel for it,
    // mirroring the scene onto the image, which is why the guard exists.
    const source = makeColorSource([[-5, 0, 0]], {
      cameras: [makeCamera({ extrinsicMatrix: LOOKING_DOWN_WORLD_X })],
    });
    const { colors, uncoloredCount } = await projectionOf(source);
    expectColorAt(colors, 0, [UNCOLORED_R, UNCOLORED_G, UNCOLORED_B]);
    expect(uncoloredCount).toBe(1);
  });

  it("leaves a point outside the frame at the fallback shade", async () => {
    // Far off-axis: projects in front of the camera but well outside its image.
    const source = makeColorSource([[1, 500, 0]], {
      cameras: [makeCamera({ extrinsicMatrix: LOOKING_DOWN_WORLD_X })],
    });
    const { colors, uncoloredCount } = await projectionOf(source);
    expectColorAt(colors, 0, [UNCOLORED_R, UNCOLORED_G, UNCOLORED_B]);
    expect(uncoloredCount).toBe(1);
  });

  it("counts only the points it could not colour", async () => {
    const source = makeColorSource(
      [
        [5, 0, 0],
        [-5, 0, 0],
      ],
      { cameras: [makeCamera({ extrinsicMatrix: LOOKING_DOWN_WORLD_X })] },
    );
    expect((await projectionOf(source)).uncoloredCount).toBe(1);
  });

  it("falls back for every point when the image could not be decoded", async () => {
    // A CORS-tainted canvas resolves to null pixels; the pass must degrade, not
    // throw, and the widget's "not seen by any camera" note explains the grey.
    const source = makeColorSource([[5, 0, 0]], {
      cameras: [makeCamera({ extrinsicMatrix: LOOKING_DOWN_WORLD_X, pixels: null })],
    });
    const { colors, uncoloredCount } = await projectionOf(source);
    expectColorAt(colors, 0, [UNCOLORED_R, UNCOLORED_G, UNCOLORED_B]);
    expect(uncoloredCount).toBe(1);
  });

  it("takes the first camera that sees the point, in declared order", async () => {
    // Not "the best" camera: no rule in the data supplies one, and first-wins at
    // least gives the same colour on every recompute.
    const source = makeColorSource([[5, 0, 0]], {
      cameras: [
        makeCamera({
          id: "a",
          extrinsicMatrix: LOOKING_DOWN_WORLD_X,
          pixels: makePixelGrid(4, 4, RED),
        }),
        makeCamera({
          id: "b",
          extrinsicMatrix: LOOKING_DOWN_WORLD_X,
          pixels: makePixelGrid(4, 4, BLUE),
        }),
      ],
    });
    const { colors } = await projectionOf(source);
    expectColorAt(colors, 0, [1, 0, 0]);
  });

  it("falls through to a later camera when the first cannot see the point", async () => {
    const blind = makeCamera({ id: "blind", extrinsicMatrix: LOOKING_DOWN_WORLD_X, pixels: null });
    const seeing = makeCamera({
      id: "seeing",
      extrinsicMatrix: LOOKING_DOWN_WORLD_X,
      pixels: makePixelGrid(4, 4, BLUE),
    });
    const source = makeColorSource([[5, 0, 0]], { cameras: [blind, seeing] });
    const { colors } = await projectionOf(source);
    expectColorAt(colors, 0, [0, 0, 1]);
  });

  it("samples the correct pixel when the decoded grid was downscaled", async () => {
    // `cameraPixels.ts` caps the decode resolution, so the calibration's pixel
    // grid and the sampled one differ. Going through normalised coordinates is
    // what keeps that correct; a direct pixel index would read the wrong half of
    // a half-size image.
    const pixels = makePixelGrid(2, 1, RED);
    // Right-hand pixel blue: at half resolution, a point on the right of the
    // 100-wide calibration frame must still land on it.
    pixels.data[4] = 0;
    pixels.data[5] = 0;
    pixels.data[6] = BYTE_MAX;

    const source = makeColorSource([[1, 0.4, 0]], {
      cameras: [
        makeCamera({
          extrinsicMatrix: LOOKING_DOWN_WORLD_X,
          imageWidth: 100,
          imageHeight: 100,
          focal: [100, 100],
          principalPoint: [50, 50],
          pixels,
        }),
      ],
    });
    const { colors } = await projectionOf(source);
    // World y = 0.4 → camera x = 0.4 → u = 90 of 100 → right half → blue.
    expectColorAt(colors, 0, [0, 0, 1]);
  });

  it("decodes each camera once for the whole cloud", async () => {
    // Per-point decoding would be catastrophic on a 30k-point cloud.
    const camera = makeCamera({ extrinsicMatrix: LOOKING_DOWN_WORLD_X });
    const source = makeColorSource(
      Array.from({ length: 20 }, (_, i) => [i + 1, 0, 0] as [number, number, number]),
      { cameras: [camera] },
    );
    await projectionOf(source);
    expect(camera.loadCount()).toBe(1);
  });

  it("stops without writing when aborted before it starts", async () => {
    const source = makeColorSource([[5, 0, 0]], {
      cameras: [makeCamera({ extrinsicMatrix: LOOKING_DOWN_WORLD_X })],
    });
    const colors = makeColorBuffer(source.pointCount);
    const aborted = new AbortController();
    aborted.abort();

    const result = await cameraProjectionColorMode.computeColors(source, colors, aborted.signal);

    // The buffer belongs to whichever pass is current; an aborted one must not
    // publish anything into it.
    expect([...colors]).toEqual([-1, -1, -1]);
    expect(result.uncoloredCount).toBeUndefined();
  });
});
