/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { LocalBBox3DAnnotation } from "$lib/annotations/annotationCollection.svelte.js";
import type { AnnotationSeedLoader, SeedLoadContext } from "$lib/annotations/seedLoaders.js";
import type { BBox3DRow } from "$lib/api/annotations.js";

/**
 * REST→local mapping for 3D boxes. Record-scoped kind: rows are kept
 * regardless of which views are displayed (a 3D box lives in the scene, not
 * in one sensor — `RECORD_SCOPED_KINDS` makes it visible everywhere,
 * including 2D projections).
 */
export const bbox3dSeedLoader: AnnotationSeedLoader = {
  kind: "bbox3d",

  async load(ctx: SeedLoadContext) {
    const rows = await ctx.gateway
      .listBBox3Ds(ctx.datasetId, { recordId: ctx.recordId })
      .catch(() => [] as BBox3DRow[]);

    return rows.map(
      (row): LocalBBox3DAnnotation => ({
        id: row.id,
        entityId: row.entity_id,
        kind: "bbox3d",
        viewId: row.view_id ?? "",
        geometry: { coords: row.coords, format: row.format, rotation: row.rotation },
        persisted: true,
        entity: row.entity_id ? ctx.entitiesById.get(row.entity_id) : undefined,
      }),
    );
  },
};
