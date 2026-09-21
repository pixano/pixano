/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BBOX3D_RESOURCE } from "./bbox3dPayloadBuilder.js";
import type { LocalBBox3DAnnotation } from "$lib/annotations/annotationCollection.svelte.js";
import type { AnnotationSeedLoader, SeedLoadContext } from "$lib/annotations/seedLoaders.js";
import type { Rotation3x3 } from "$lib/annotations/types.js";
import type { BBox3DRow } from "$lib/api/annotations.js";

/** A row-major 3×3 matrix has exactly nine entries. */
const ROTATION_LENGTH = 9;

/**
 * The one boundary where unvalidated rotations enter: a server row is typed
 * `number[]`, but every consumer downstream feeds it to `Matrix3.fromArray`,
 * which reads nine slots and produces NaN geometry from a shorter array — and
 * NaN defeats the renderers' own "is this projectable?" guards, since every
 * comparison with NaN is false. Anything malformed is dropped to `undefined`,
 * which every consumer already handles as "no rotation".
 */
function toRotation3x3(rotation: number[] | undefined): Rotation3x3 | undefined {
  if (!rotation || rotation.length !== ROTATION_LENGTH) return undefined;
  if (!rotation.every((n) => Number.isFinite(n))) return undefined;
  return rotation as Rotation3x3;
}

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
      .listAnnotations<BBox3DRow>(ctx.datasetId, BBOX3D_RESOURCE, { recordId: ctx.recordId })
      .catch(() => [] as BBox3DRow[]);

    return rows.map(
      (row): LocalBBox3DAnnotation => ({
        id: row.id,
        entityId: row.entity_id,
        kind: "bbox3d",
        viewId: row.view_id ?? "",
        geometry: { coords: row.coords, format: row.format, rotation: toRotation3x3(row.rotation) },
        persisted: true,
        entity: row.entity_id ? ctx.entitiesById.get(row.entity_id) : undefined,
      }),
    );
  },
};
