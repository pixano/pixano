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
import type { AnnotationSeedLoader, SeedLoadContext, ViewInfo } from "./seedLoaders.js";

/**
 * The columns every view-scoped annotation row carries, whatever its kind:
 * an identity, its parent entity, and the view it was drawn in.
 */
export interface ViewScopedRow {
  id: string;
  entity_id: string;
  view_id: string;
}

/**
 * Builds the REST→local mapping that every view-scoped kind would otherwise
 * repeat verbatim: fetch the record's rows once, drop the ones whose view is
 * not displayed, and wrap each survivor in the shared `LocalAnnotation`
 * envelope.
 *
 * A kind supplies only what is genuinely its own — the resource to read and how
 * one row becomes geometry. Everything else is a decision that must not differ
 * between kinds: the envelope's field mapping, the view filter, and the failure
 * policy (a failed fetch seeds nothing rather than breaking the whole record).
 * Keeping them here means they cannot drift apart one copy at a time.
 *
 * Lives in its own module rather than in `seedLoaders.ts` on purpose: the
 * registry there imports every kind, so a kind importing a *value* back from it
 * would close a runtime import cycle. This module only imports types.
 *
 * Record-scoped kinds (`bbox3d`) do not use this: they keep every row
 * regardless of the displayed views, which is the one rule this helper encodes.
 */
export function createViewScopedSeedLoader<
  K extends AnnotationKind,
  TRow extends ViewScopedRow,
>(spec: {
  kind: K;
  resource: string;
  /** Returns `null` to drop a row the kind considers malformed. */
  toGeometry: (row: TRow, view: ViewInfo) => GeometryByKind[K] | null;
}): AnnotationSeedLoader {
  return {
    kind: spec.kind,

    async load(ctx: SeedLoadContext) {
      const rows = await ctx.gateway
        .listAnnotations<TRow>(ctx.datasetId, spec.resource, { recordId: ctx.recordId })
        .catch(() => [] as TRow[]);

      const annotations: LocalAnnotation[] = [];
      for (const row of rows) {
        const view = ctx.views.get(row.view_id);
        if (!view) continue;
        const geometry = spec.toGeometry(row, view);
        if (geometry === null) continue;

        annotations.push({
          id: row.id,
          entityId: row.entity_id,
          kind: spec.kind,
          viewId: view.id,
          geometry,
          persisted: true,
          entity: ctx.entitiesById.get(row.entity_id),
        });
      }
      return annotations;
    },
  };
}
