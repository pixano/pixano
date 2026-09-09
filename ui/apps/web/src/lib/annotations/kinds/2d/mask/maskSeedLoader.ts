/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { MASK_RESOURCE } from "./maskPayloadBuilder.js";
import type { LocalMask } from "$lib/annotations/annotationCollection.svelte.js";
import { createViewScopedSeedLoader } from "$lib/annotations/viewScopedSeedLoader.js";

/** Minimal shape of a mask row as returned by `GET /datasets/:id/masks`. */
export interface MaskRow {
  id: string;
  record_id: string;
  entity_id: string;
  view_id: string;
  /** `[height, width]`; `[0, 0]` is the backend's "empty mask" sentinel. */
  size: number[];
  /** COCO run-length encoding, serialized to a utf-8 string by the backend. */
  counts: string;
}

/** A mask needs a positive grid and a non-empty encoding to be drawable. */
function toGeometry(row: MaskRow): LocalMask["geometry"] | null {
  const [height, width] = row.size ?? [];
  if (!Number.isInteger(height) || !Number.isInteger(width) || height <= 0 || width <= 0) {
    return null;
  }
  if (typeof row.counts !== "string" || row.counts.length === 0) return null;
  return { size: [height, width], counts: row.counts };
}

/**
 * REST→local mapping for masks. Unlike bboxes there is no coordinate
 * conversion: the RLE stays in the image grid it was encoded against (`size`)
 * and the renderer scales it onto the frame. Rows carrying the backend's
 * empty-mask sentinel are dropped by `toGeometry` rather than seeded as
 * undrawable annotations.
 */
export const maskSeedLoader = createViewScopedSeedLoader<"mask", MaskRow>({
  kind: "mask",
  resource: MASK_RESOURCE,
  toGeometry,
});
