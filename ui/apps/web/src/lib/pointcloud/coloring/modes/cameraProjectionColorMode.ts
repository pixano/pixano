/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Camera } from "lucide-svelte";

import type {
  PixelGrid,
  PointCloudColorMode,
  PointCloudColorSource,
  ProjectionCamera,
} from "../colorMode.js";
import { writeUncolored } from "../colorRamp.js";

/** Row-major 4×4 indices of the rows that produce a transformed XYZ. */
const ROW_X = 0;
const ROW_Y = 4;
const ROW_Z = 8;
const COL_X = 0;
const COL_Y = 1;
const COL_Z = 2;
const COL_TRANSLATION = 3;

/** Bytes per pixel in a `PixelGrid`'s RGBA data. */
const RGBA_STRIDE = 4;
const BYTE_MAX = 255;

/** A camera whose image was decoded, paired with its pixels. */
interface ReadyCamera {
  camera: ProjectionCamera;
  pixels: PixelGrid;
}

/**
 * Projects each point into every calibrated camera and paints it with the
 * pixel it lands on, giving the cloud the scene's real colours.
 *
 * Cameras are tried in the dataset's declared order and the first one that sees
 * a point wins. Picking the "best" camera instead (most central, nearest) would
 * need a rule the data does not supply, and first-wins is at least stable: the
 * same point gets the same colour on every recompute.
 *
 * **No occlusion test.** A point behind a wall still projects onto the wall's
 * pixel and takes its colour, because answering "is this point visible from
 * that camera?" needs a depth buffer rendered per camera. Every lidar viewer
 * that does this cheaply has the same artefact; the honest version is a
 * separate piece of work, not a tweak to this loop.
 *
 * Lens distortion is ignored, matching the 3D-box projection in
 * `kinds/2d/bbox3d/bbox3dRenderer2D.ts` — the two must agree, or a box would
 * not line up with the points inside it.
 */
export const cameraProjectionColorMode: PointCloudColorMode = {
  id: "camera-projection",
  label: "Camera colours",
  icon: Camera,

  unavailableReason(source: PointCloudColorSource) {
    if (source.cameras.length === 0) return "This record has no calibrated camera";
    return null;
  },

  async computeColors(source: PointCloudColorSource, out: Float32Array, signal: AbortSignal) {
    // Decode every camera up front and in parallel: the projection loop is
    // synchronous once the pixels are in hand, and doing it per camera would
    // serialise the network on the number of sensors.
    const decoded = await Promise.all(
      source.cameras.map(async (camera): Promise<ReadyCamera | null> => {
        const pixels = await camera.loadPixels(signal);
        return pixels ? { camera, pixels } : null;
      }),
    );
    if (signal.aborted) return {};

    const ready = decoded.filter((entry): entry is ReadyCamera => entry !== null);
    const lance: [number, number, number] = [0, 0, 0];
    let uncoloredCount = 0;

    for (let i = 0; i < source.pointCount; i++) {
      source.toLance(i, lance);
      let painted = false;

      for (const { camera, pixels } of ready) {
        if (samplePointColor(lance, camera, pixels, out, i * 3)) {
          painted = true;
          break;
        }
      }

      if (!painted) {
        writeUncolored(out, i * 3);
        uncoloredCount++;
      }
    }

    return { uncoloredCount };
  },
};

/**
 * Pinhole-project one world point into a camera and write the pixel it lands
 * on. Returns false — leaving `out` untouched — when the point is behind the
 * camera or outside the frame, so the caller can try the next one.
 */
function samplePointColor(
  point: [number, number, number],
  camera: ProjectionCamera,
  pixels: PixelGrid,
  out: Float32Array,
  offset: number,
): boolean {
  const m = camera.calibration.extrinsicMatrix;
  const [x, y, z] = point;

  const camX =
    m[ROW_X + COL_X] * x + m[ROW_X + COL_Y] * y + m[ROW_X + COL_Z] * z + m[ROW_X + COL_TRANSLATION];
  const camY =
    m[ROW_Y + COL_X] * x + m[ROW_Y + COL_Y] * y + m[ROW_Y + COL_Z] * z + m[ROW_Y + COL_TRANSLATION];
  const camZ =
    m[ROW_Z + COL_X] * x + m[ROW_Z + COL_Y] * y + m[ROW_Z + COL_Z] * z + m[ROW_Z + COL_TRANSLATION];

  // `!(camZ > 0)` rather than `camZ <= 0`: every comparison with NaN is false,
  // so the plain form would wave a NaN from a corrupt matrix through into a
  // pixel index. Same guard as the bbox3d projection.
  if (!(camZ > 0)) return false;

  const { f, c } = camera.calibration;
  const u = (f[0] * camX) / camZ + c[0];
  const v = (f[1] * camY) / camZ + c[1];

  // The calibration's principal point is expressed in the *stored* image's
  // pixel grid; the decoded bitmap can differ if the backend ever serves a
  // resized copy. Going through normalised coordinates makes the sampling
  // correct either way.
  const calibrationWidth = camera.imageWidth || pixels.width;
  const calibrationHeight = camera.imageHeight || pixels.height;
  const px = Math.floor((u / calibrationWidth) * pixels.width);
  const py = Math.floor((v / calibrationHeight) * pixels.height);
  if (px < 0 || px >= pixels.width || py < 0 || py >= pixels.height) return false;

  const base = (py * pixels.width + px) * RGBA_STRIDE;
  out[offset] = pixels.data[base] / BYTE_MAX;
  out[offset + 1] = pixels.data[base + 1] / BYTE_MAX;
  out[offset + 2] = pixels.data[base + 2] / BYTE_MAX;
  return true;
}
