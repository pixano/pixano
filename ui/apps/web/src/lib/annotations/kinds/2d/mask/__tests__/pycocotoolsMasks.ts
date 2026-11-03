/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { MaskBounds } from "../maskRaster.js";

/**
 * Masks as the backend stores them when a segmentation job writes them: encoded
 * by pycocotools (`CompressedRLE.from_mask`, i.e. `pycocotools.mask.encode` of a
 * Fortran-ordered `[height, width]` array), `counts` sent as the utf-8 string
 * `CompressedRLE._serialize_counts` makes of them. Nothing here was encoded by
 * the interface, so a test decoding them checks the interface against the
 * encoder the server uses, not against its own inverse.
 *
 * The image is wider than tall, so a mask read row-major, or with `size` taken
 * as `[width, height]`, lands somewhere else. Produced by:
 *
 *   import numpy as np
 *   from pycocotools import mask as mask_api
 *   from pixano.features import CompressedRLE
 *
 *   def triangle(dx=0, dy=0):
 *       m = np.zeros((24, 40), dtype=np.uint8)
 *       for c in range(9, 29):
 *           m[5 + dy : 5 + (c - 9) // 2 + 1 + dy, c + dx] = 1
 *       return m
 *
 *   corner = np.zeros((24, 40), dtype=np.uint8)
 *   corner[0:7, 0:12] = 1
 *
 *   for m in (triangle(), triangle(3, 2), corner):
 *       rle = CompressedRLE.from_mask(m).model_dump()
 *       raw = mask_api.encode(np.asfortranarray(m))
 *       print(rle["size"], rle["counts"], mask_api.toBbox(raw), mask_api.area(raw))
 *
 * `bounds` and `area` are pycocotools' own reading of each mask (`toBbox`,
 * `area`), so they are the expected values, not a second decode of ours.
 */
export interface PycocotoolsMask {
  /** `[height, width]` of the image the mask was segmented on. */
  size: [number, number];
  counts: string;
  /** `toBbox`: `[x, y, width, height]` of the painted pixels, in grid pixels. */
  bounds: MaskBounds;
  /** `area`: how many pixels are painted. */
  area: number;
}

/** The image the masks were segmented on: 40 px wide, 24 px tall. */
export const IMAGE_SIZE: [number, number] = [24, 40];

/**
 * A triangle, as a dataset of drawn shapes holds them: one more painted row every second
 * column, so its run lengths change from one column to the next — the
 * encoding then carries negative differences, written on several characters.
 */
export const TRIANGLE: PycocotoolsMask = {
  size: IMAGE_SIZE,
  counts: "m61g0001O001O001O001O001O001O001O001O001O0S8",
  bounds: { x: 9, y: 5, width: 20, height: 10 },
  area: 110,
};

/** How far `TRIANGLE_MOVED` is from `TRIANGLE`, in grid pixels. */
export const TRIANGLE_SHIFT = { columns: 3, rows: 2 };

/** `TRIANGLE` moved `TRIANGLE_SHIFT` right and down, as pycocotools encodes it. */
export const TRIANGLE_MOVED: PycocotoolsMask = {
  size: IMAGE_SIZE,
  counts: "W91g0001O001O001O001O001O001O001O001O001O0i5",
  bounds: { x: 12, y: 7, width: 20, height: 10 },
  area: 110,
};

/**
 * An object cut by the image's top-left corner. Its first pixel is painted, so
 * pycocotools starts its counts with an empty background run, a `0`.
 */
export const CORNER: PycocotoolsMask = {
  size: IMAGE_SIZE,
  counts: "07a0000000000000000000000Pe0",
  bounds: { x: 0, y: 0, width: 12, height: 7 },
  area: 84,
};

/** How many pixels a run-length list paints: every second run, from the second. */
export function paintedArea(runs: number[]): number {
  return runs.reduce((sum, run, index) => (index % 2 === 1 ? sum + run : sum), 0);
}
