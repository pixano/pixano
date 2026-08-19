/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { CLASSIFICATION_RESOURCE } from "./classificationPayloadBuilder.js";
import type { ClassificationGeometry } from "./classificationTypes.js";
import { createViewScopedSeedLoader } from "$lib/annotations/viewScopedSeedLoader.js";

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
 * REST→local mapping for classifications. There is no geometry to convert — a
 * classification annotates the whole view, so its payload is the label list and
 * nothing else.
 */
export const classificationSeedLoader = createViewScopedSeedLoader<
  "classification",
  ClassificationRow
>({
  kind: "classification",
  resource: CLASSIFICATION_RESOURCE,
  toGeometry,
});
