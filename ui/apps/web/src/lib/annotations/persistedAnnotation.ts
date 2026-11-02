/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  AnnotationKind,
  GeometryByKind,
  LocalAnnotation,
} from "./annotationCollection.svelte.js";
import { reviewOf } from "./reviewStatus.js";
import type { SeedLoadContext } from "./seedLoaders.js";
import type { EntityAnnotationColumns } from "$lib/api/annotations.js";

/** The columns the envelope reads from any stored annotation row. */
export interface PersistedRow extends EntityAnnotationColumns {
  id: string;
  entity_id: string;
}

/**
 * What only the seed loader knows: the kind, the view it resolved, the geometry
 * it parsed — and the kind's score columns.
 */
export interface PersistedAnnotationFields<K extends AnnotationKind> {
  kind: K;
  viewId: string;
  geometry: GeometryByKind[K];
  /**
   * The columns of the kind's rows that hold a model's score, in the order they
   * are read — the score fields of the kind's backend schema. The kind states
   * them here, next to its row mapping, so no shared module knows a kind's
   * columns: the review reads the score from them. Omitted by a kind with no
   * score.
   */
  scoreFields?: readonly string[];
}

/**
 * Wrap a stored row in the `LocalAnnotation` envelope: its identity, its
 * entity's label snapshot, and its provenance and review status.
 *
 * Every seed loader goes through this one function — the view-scoped helper
 * and the loaders that keep rows record-wide alike — so a field the envelope
 * gains reaches every kind at once. The review state is the case in point: a
 * loader that built its envelope by hand would load a model's rows as if a
 * person had drawn them, and nothing would fail.
 *
 * Imports only types and the type-only `reviewStatus.ts`, so a kind may import
 * it without closing an import cycle through a registry.
 */
export function persistedAnnotation<K extends AnnotationKind>(
  row: PersistedRow,
  fields: PersistedAnnotationFields<K>,
  ctx: Pick<SeedLoadContext, "entitiesById">,
): LocalAnnotation<GeometryByKind[K]> {
  return {
    id: row.id,
    entityId: row.entity_id,
    kind: fields.kind,
    viewId: fields.viewId,
    geometry: fields.geometry,
    persisted: true,
    entity: row.entity_id ? ctx.entitiesById.get(row.entity_id) : undefined,
    review: reviewOf(row, fields.scoreFields ?? []),
  };
}
