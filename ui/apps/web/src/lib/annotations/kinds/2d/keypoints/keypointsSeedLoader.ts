/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { KEYPOINTS_RESOURCE } from "./keypointsPayloadBuilder.js";
import type { KeypointsGeometry, KeypointState } from "./keypointsTypes.js";
import { createViewScopedSeedLoader } from "$lib/annotations/viewScopedSeedLoader.js";

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
 * REST→local mapping for keypoint skeletons. Coordinates arrive already
 * normalized, so the view is needed only to scope the row, not to convert it.
 */
export const keypointsSeedLoader = createViewScopedSeedLoader<"keypoints", KeypointsRow>({
  kind: "keypoints",
  resource: KEYPOINTS_RESOURCE,
  toGeometry,
});
