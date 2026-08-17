/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { MaskGeometry } from "./maskTypes.js";
import {
  canvasAlphaToRle,
  rleFrString,
  rleToBitmapCanvas,
  rleToString,
} from "$lib/utils/maskUtils";

/**
 * The one place that converts between a `MaskGeometry` (what the collection and
 * the backend hold) and a pixel raster (what the renderer draws and the brush
 * paints on). Keeping both directions here is what stops the renderer and the
 * tool from each growing their own half-correct copy of the RLE contract.
 *
 * Both directions go through `$lib/utils/maskUtils`, whose `rleToBitmapCanvas`
 * and `canvasAlphaToRle` are exact inverses: column-major (Fortran) order,
 * foreground = alpha > 0.
 */

/** Any 2D raster we can both draw from and read back. */
export type MaskCanvas = OffscreenCanvas;

/**
 * `OffscreenCanvas` is missing in some non-browser runtimes (the test DOM among
 * them). Rasterising is a display concern, so callers degrade to "draw nothing"
 * rather than throw — mirroring how the bbox3d projection handles a missing
 * calibration.
 */
function canRaster(): boolean {
  return typeof OffscreenCanvas !== "undefined";
}

/** A blank painting surface matching a mask grid, or null if unsupported. */
export function createMaskCanvas(size: [number, number]): MaskCanvas | null {
  if (!canRaster()) return null;
  const [height, width] = size;
  if (height <= 0 || width <= 0) return null;
  return new OffscreenCanvas(width, height);
}

/**
 * Decode a mask into an opaque white raster on a transparent background.
 * White rather than the display colour because tinting is a separate step —
 * the decode result can then be reused across colour changes.
 */
export function decodeMask(geometry: MaskGeometry): MaskCanvas | null {
  if (!canRaster()) return null;
  const counts = rleFrString(geometry.counts);
  if (counts.length === 0) return null;
  try {
    return rleToBitmapCanvas(counts, geometry.size);
  } catch {
    // A malformed encoding should hide one mask, not break the whole scene.
    return null;
  }
}

/**
 * Recolour a decoded mask, preserving its alpha. `source-in` keeps the incoming
 * fill only where the raster is already opaque, which is exactly the mask's
 * footprint.
 */
export function tintMask(source: MaskCanvas, color: string, opacity: number): MaskCanvas | null {
  const tinted = createMaskCanvas([source.height, source.width]);
  if (!tinted) return null;
  const ctx = tinted.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(source, 0, 0);
  ctx.globalCompositeOperation = "source-in";
  ctx.globalAlpha = opacity;
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, tinted.width, tinted.height);
  return tinted;
}

/**
 * Read a painted raster back into a `MaskGeometry`. Returns null when nothing
 * was painted, so an empty gesture produces no annotation instead of a mask the
 * backend would store as its `[0, 0]` empty sentinel.
 */
export function encodeMask(canvas: MaskCanvas): MaskGeometry | null {
  const { counts, size } = canvasAlphaToRle(canvas);
  // A blank canvas encodes as a single background run covering every pixel.
  if (counts.length <= 1) return null;
  return { size, counts: rleToString(counts) };
}
