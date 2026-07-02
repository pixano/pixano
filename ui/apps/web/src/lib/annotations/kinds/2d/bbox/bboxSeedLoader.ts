/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { LocalBBox } from "$lib/annotations/annotationCollection.svelte.js";
import type { AnnotationSeedLoader, SeedLoadContext } from "$lib/annotations/seedLoaders.js";
import type { CoordsNorm } from "$lib/annotations/types.js";
import type { BBoxRow } from "$lib/api/annotations.js";

/**
 * REST→local mapping for 2D boxes: one record-scoped fetch, rows resolved to
 * their displayed view (by image row id or legacy logical name), coords
 * normalized to xywh in [0,1] using that view's dimensions. Rows whose view
 * is not displayed are skipped, matching the previous per-view filtering.
 */
export const bboxSeedLoader: AnnotationSeedLoader = {
  kind: "bbox",

  async load(ctx: SeedLoadContext) {
    const rows = await ctx.gateway
      .listBBoxes(ctx.datasetId, { recordId: ctx.recordId })
      .catch(() => [] as BBoxRow[]);

    const annotations: LocalBBox[] = [];
    for (const row of rows) {
      const view = ctx.views.get(row.view_id);
      if (!view || !Array.isArray(row.coords) || row.coords.length !== 4) continue;

      // Backend stores xywh or xyxy, pixel-space or normalized; we normalise
      // to xywh in [0,1] here.
      let [x, y, w, h] = row.coords;
      if (row.format === "xyxy") {
        w = w - x;
        h = h - y;
      }
      const iw = view.width || 1;
      const ih = view.height || 1;
      const coordsNorm: CoordsNorm = row.is_normalized
        ? [x, y, w, h]
        : [x / iw, y / ih, w / iw, h / ih];

      annotations.push({
        id: row.id,
        entityId: row.entity_id,
        kind: "bbox",
        viewId: view.id,
        geometry: coordsNorm,
        persisted: true,
        entity: ctx.entitiesById.get(row.entity_id),
      });
    }
    return annotations;
  },
};
