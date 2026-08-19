/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { MULTI_PATH_RESOURCE } from "./multiPathPayloadBuilder.js";
import { minPointsFor, type MultiPathGeometry } from "./multiPathTypes.js";
import { createViewScopedSeedLoader } from "$lib/annotations/viewScopedSeedLoader.js";

/** Minimal shape of a multi-path row as returned by `GET …/multi-paths`. */
export interface MultiPathRow {
  id: string;
  record_id: string;
  entity_id: string;
  view_id: string;
  /** Flat, normalized `[x0, y0, x1, y1, …]` across all sub-paths. */
  coords: number[];
  num_points: number[];
  is_closed: boolean;
}

/**
 * Re-check the invariants the backend enforces on write, because a row can also
 * arrive from an import that bypassed the API. A `num_points` that disagrees
 * with `coords` would otherwise slice sub-paths at the wrong offsets and draw a
 * shape that exists nowhere in the data.
 */
function toGeometry(row: MultiPathRow): MultiPathGeometry | null {
  const coords = row.coords;
  if (!Array.isArray(coords) || coords.length === 0 || coords.length % 2 !== 0) return null;
  if (!coords.every((c) => Number.isFinite(c) && c >= 0 && c <= 1)) return null;

  const numPoints = row.num_points;
  if (!Array.isArray(numPoints) || numPoints.length === 0) return null;
  if (!numPoints.every((n) => Number.isInteger(n) && n > 0)) return null;

  const isClosed = row.is_closed === true;
  const total = numPoints.reduce((sum, n) => sum + n, 0);
  if (total * 2 !== coords.length) return null;

  const minPoints = minPointsFor(isClosed);
  if (!numPoints.every((n) => n >= minPoints)) return null;

  return { coords: [...coords], numPoints: [...numPoints], isClosed };
}

/**
 * REST→local mapping for polygons and polylines. Both are the same kind, told
 * apart by `is_closed`; `toGeometry` also enforces the backend's
 * `sum(num_points) * 2 === coords.length` invariant before seeding.
 */
export const multiPathSeedLoader = createViewScopedSeedLoader<"multi_path", MultiPathRow>({
  kind: "multi_path",
  resource: MULTI_PATH_RESOURCE,
  toGeometry,
});
