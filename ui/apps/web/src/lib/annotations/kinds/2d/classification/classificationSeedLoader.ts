/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { CLASSIFICATION_RESOURCE } from "./classificationPayloadBuilder.js";
import type { ClassificationGeometry } from "./classificationTypes.js";
import type { LocalClassification } from "$lib/annotations/annotationCollection.svelte.js";
import type { AnnotationSeedLoader, SeedLoadContext } from "$lib/annotations/seedLoaders.js";

/** Minimal shape of a row as returned by `GET …/classifications`. */
export interface ClassificationRow {
  id: string;
  record_id: string;
  entity_id: string;
  view_id: string;
  labels: string[];
  confidences: number[];
}

/**
 * Re-check the backend's invariant, because a row can also arrive from an
 * import that bypassed the API: a labels/confidences mismatch would render
 * chips whose confidence belongs to a different class.
 */
function toGeometry(row: ClassificationRow): ClassificationGeometry | null {
  const labels = row.labels;
  const confidences = row.confidences;
  if (!Array.isArray(labels) || labels.length === 0) return null;
  if (!labels.every((label) => typeof label === "string" && label.length > 0)) return null;
  if (!Array.isArray(confidences) || confidences.length !== labels.length) return null;
  if (!confidences.every((c) => Number.isFinite(c))) return null;

  return { labels: [...labels], confidences: [...confidences] };
}

/**
 * REST→local mapping for classifications: one record-scoped fetch, rows
 * resolved to their displayed view (by image row id or legacy logical name).
 *
 * There is no coordinate conversion — a classification annotates the whole
 * view, so its payload is the label list and nothing else.
 */
export const classificationSeedLoader: AnnotationSeedLoader = {
  kind: "classification",

  async load(ctx: SeedLoadContext) {
    const rows = await ctx.gateway
      .listAnnotations<ClassificationRow>(ctx.datasetId, CLASSIFICATION_RESOURCE, {
        recordId: ctx.recordId,
      })
      .catch(() => [] as ClassificationRow[]);

    const annotations: LocalClassification[] = [];
    for (const row of rows) {
      const view = ctx.views.get(row.view_id);
      if (!view) continue;
      const geometry = toGeometry(row);
      if (!geometry) continue;

      annotations.push({
        id: row.id,
        entityId: row.entity_id,
        kind: "classification",
        viewId: view.id,
        geometry,
        persisted: true,
        entity: ctx.entitiesById.get(row.entity_id),
      });
    }
    return annotations;
  },
};
