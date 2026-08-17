/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { MASK_RESOURCE } from "./maskPayloadBuilder.js";
import type { LocalMask } from "$lib/annotations/annotationCollection.svelte.js";
import type { AnnotationSeedLoader, SeedLoadContext } from "$lib/annotations/seedLoaders.js";

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
 * REST→local mapping for masks: one record-scoped fetch, rows resolved to
 * their displayed view (by image row id or legacy logical name). Rows whose
 * view is not displayed are skipped, as for 2D boxes.
 *
 * Unlike bboxes there is no coordinate conversion here — the RLE stays in the
 * image grid it was encoded against (`size`), and the renderer scales it onto
 * the frame. Rows the backend stores as its empty-mask sentinel (`size [0,0]`,
 * empty `counts`) are dropped rather than seeded as undrawable annotations.
 */
export const maskSeedLoader: AnnotationSeedLoader = {
  kind: "mask",

  async load(ctx: SeedLoadContext) {
    const rows = await ctx.gateway
      .listAnnotations<MaskRow>(ctx.datasetId, MASK_RESOURCE, { recordId: ctx.recordId })
      .catch(() => [] as MaskRow[]);

    const annotations: LocalMask[] = [];
    for (const row of rows) {
      const view = ctx.views.get(row.view_id);
      if (!view) continue;
      const geometry = toGeometry(row);
      if (!geometry) continue;

      annotations.push({
        id: row.id,
        entityId: row.entity_id,
        kind: "mask",
        viewId: view.id,
        geometry,
        persisted: true,
        entity: ctx.entitiesById.get(row.entity_id),
      });
    }
    return annotations;
  },
};
