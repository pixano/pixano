/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { PixelGrid, ProjectionCamera } from "./coloring/colorMode.js";
import type { CameraCalibration } from "$lib/annotations/types.js";

/**
 * Longest edge a camera image is decoded at. A record with six 1600×900
 * cameras would otherwise hold ~35 MB of RGBA for as long as the widget lives;
 * the projection samples through normalised coordinates, so a smaller grid
 * costs a little colour precision and nothing in correctness.
 */
const MAX_DECODED_EDGE = 1024;

export interface ProjectionCameraSpec {
  id: string;
  name: string;
  url: string;
  imageWidth: number;
  imageHeight: number;
  calibration: CameraCalibration;
}

/**
 * A `ProjectionCamera` backed by the browser's image decoder.
 *
 * The decode is lazy and memoised on the first `loadPixels`: a user who never
 * opens the projection mode never pays for it, and switching back and forth
 * between modes does not re-download six images. Failures resolve to `null`
 * rather than rejecting — one unreadable camera should cost its own colours,
 * not the whole colouring pass.
 */
export function createProjectionCamera(spec: ProjectionCameraSpec): ProjectionCamera {
  let pending: Promise<PixelGrid | null> | null = null;

  return {
    id: spec.id,
    name: spec.name,
    imageWidth: spec.imageWidth,
    imageHeight: spec.imageHeight,
    calibration: spec.calibration,
    loadPixels(signal: AbortSignal) {
      pending ??= decodeImage(spec.url, signal);
      return pending;
    },
  };
}

function decodeImage(url: string, signal: AbortSignal): Promise<PixelGrid | null> {
  return new Promise((resolve) => {
    if (signal.aborted) {
      resolve(null);
      return;
    }

    const image = new Image();
    // Media may be served from another origin. Requesting CORS is what lets the
    // canvas be read back at all; without it `getImageData` throws on a tainted
    // canvas, which the try/catch below turns into "this camera has no pixels".
    image.crossOrigin = "anonymous";

    const onAbort = () => resolve(null);
    signal.addEventListener("abort", onAbort, { once: true });
    const settle = (value: PixelGrid | null) => {
      signal.removeEventListener("abort", onAbort);
      resolve(value);
    };

    image.onload = () => settle(toPixelGrid(image));
    image.onerror = () => settle(null);
    image.src = url;
  });
}

function toPixelGrid(image: HTMLImageElement): PixelGrid | null {
  const scale = Math.min(1, MAX_DECODED_EDGE / Math.max(image.naturalWidth, image.naturalHeight));
  const width = Math.max(1, Math.round(image.naturalWidth * scale));
  const height = Math.max(1, Math.round(image.naturalHeight * scale));

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return null;

  context.drawImage(image, 0, 0, width, height);
  try {
    const { data } = context.getImageData(0, 0, width, height);
    return { width, height, data };
  } catch {
    // Tainted canvas: the media origin refused CORS. Nothing to recover, and
    // the mode already reports points it could not colour.
    return null;
  }
}
