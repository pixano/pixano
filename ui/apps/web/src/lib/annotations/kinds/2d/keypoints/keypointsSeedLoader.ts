/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { KEYPOINTS_RESOURCE } from "./keypointsPayloadBuilder.js";
import type { KeypointsGeometry, KeypointState } from "./keypointsTypes.js";
import type { LocalKeypoints } from "$lib/annotations/annotationCollection.svelte.js";
import type { AnnotationSeedLoader, SeedLoadContext } from "$lib/annotations/seedLoaders.js";

/** Minimal shape of a keypoints row as returned by `GET /datasets/:id/keypoints`. */
export interface KeypointsRow {
  id: string;
  record_id: string;
  entity_id: string;
  view_id: string;
  template_id: string;
  /** Flat, normalized `[x0, y0, x1, y1, …]`. */
  coords: number[];
  states: string[];
}

const VALID_STATES: ReadonlySet<string> = new Set(["visible", "invisible", "hidden"]);

/**
 * Re-check the invariants the backend enforces on write, because a row can also
 * arrive from an import that bypassed the API. A skeleton with a stray state or
 * a dangling coordinate would otherwise render as a half-drawn shape whose
 * points and states no longer line up.
 */
function toGeometry(row: KeypointsRow): KeypointsGeometry | null {
  const coords = row.coords;
  if (!Array.isArray(coords) || coords.length === 0 || coords.length % 2 !== 0) return null;
  if (!coords.every((c) => Number.isFinite(c) && c >= 0)) return null;

  const states = row.states;
  if (!Array.isArray(states) || states.length !== coords.length / 2) return null;
  if (!states.every((s) => VALID_STATES.has(s))) return null;

  return {
    templateId: row.template_id ?? "",
    coords: [...coords],
    states: [...states] as KeypointState[],
  };
}

/**
 * REST→local mapping for keypoint skeletons: one record-scoped fetch, rows
 * resolved to their displayed view (by image row id or legacy logical name).
 *
 * Coordinates stay normalized, as stored — the renderer scales them onto the
 * frame, exactly as for a bbox.
 */
export const keypointsSeedLoader: AnnotationSeedLoader = {
  kind: "keypoints",

  async load(ctx: SeedLoadContext) {
    const rows = await ctx.gateway
      .listAnnotations<KeypointsRow>(ctx.datasetId, KEYPOINTS_RESOURCE, { recordId: ctx.recordId })
      .catch(() => [] as KeypointsRow[]);

    const annotations: LocalKeypoints[] = [];
    for (const row of rows) {
      const view = ctx.views.get(row.view_id);
      if (!view) continue;
      const geometry = toGeometry(row);
      if (!geometry) continue;

      annotations.push({
        id: row.id,
        entityId: row.entity_id,
        kind: "keypoints",
        viewId: view.id,
        geometry,
        persisted: true,
        entity: ctx.entitiesById.get(row.entity_id),
      });
    }
    return annotations;
  },
};
