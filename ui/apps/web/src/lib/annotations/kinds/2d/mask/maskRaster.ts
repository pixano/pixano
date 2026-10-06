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
/**
 * Move a mask within its own pixel grid.
 *
 * The grid is fixed — it is the media's resolution, recorded in `size` — so a
 * translation redraws the same stamp at an offset and lets whatever crosses an
 * edge fall outside the canvas. That clipping is deliberate: the alternative,
 * growing `size` to fit, would silently re-scale the mask against the image it
 * annotates.
 *
 * Offsets are in grid pixels and rounded, because RLE addresses whole pixels —
 * a fractional shift has no representation.
 */
/** Tight box around the painted pixels, in the mask's own grid. */
export interface MaskBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Where the paint actually is inside the grid.
 *
 * Read straight off the run lengths rather than by scanning a rasterised
 * canvas: a mask's grid is the media's full resolution, so scanning pixels to
 * find a stamp that may cover a corner of it would cost far more than walking
 * the runs that describe it. Column-major, matching the COCO layout the backend
 * stores — index `i` sits at row `i % height`, column `i / height`.
 *
 * Returns null for an empty mask, which has no position to speak of.
 */
export function maskBounds(counts: number[], size: [number, number]): MaskBounds | null {
  const [height, width] = size;
  if (height <= 0 || width <= 0) return null;

  let minX = width;
  let minY = height;
  let maxX = -1;
  let maxY = -1;
  let index = 0;
  let painted = false;

  for (const run of counts) {
    if (painted && run > 0) {
      const first = index;
      const last = index + run - 1;
      const firstCol = Math.floor(first / height);
      const lastCol = Math.floor(last / height);
      if (firstCol < minX) minX = firstCol;
      if (lastCol > maxX) maxX = lastCol;
      // A run spanning more than one column covers every row it passes through.
      if (lastCol > firstCol) {
        minY = 0;
        maxY = height - 1;
      } else {
        const firstRow = first % height;
        const lastRow = last % height;
        if (firstRow < minY) minY = firstRow;
        if (lastRow > maxY) maxY = lastRow;
      }
    }
    index += run;
    painted = !painted;
  }

  if (maxX < 0 || maxY < 0) return null;
  return { x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1 };
}

export function translateMask(
  geometry: MaskGeometry,
  dxPixels: number,
  dyPixels: number,
): MaskGeometry | null {
  const dx = Math.round(dxPixels);
  const dy = Math.round(dyPixels);
  if (dx === 0 && dy === 0) return geometry;

  const source = decodeMask(geometry);
  if (!source) return null;
  const moved = createMaskCanvas(geometry.size);
  if (!moved) return null;
  const ctx = moved.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(source, dx, dy);
  return encodeMask(moved);
}

export function encodeMask(canvas: MaskCanvas): MaskGeometry | null {
  const { counts, size } = canvasAlphaToRle(canvas);
  // A blank canvas encodes as a single background run covering every pixel.
  if (counts.length <= 1) return null;
  return { size, counts: rleToString(counts) };
}
