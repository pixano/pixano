/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BBOX_RESOURCE } from "./bboxPayloadBuilder.js";
import type { ViewInfo } from "$lib/annotations/seedLoaders.js";
import type { CoordsNorm } from "$lib/annotations/types.js";
import { createViewScopedSeedLoader } from "$lib/annotations/viewScopedSeedLoader.js";
import type { BBoxRow } from "$lib/api/annotations.js";

/**
 * The backend stores boxes as xywh or xyxy, in pixel space or already
 * normalized; the local model knows only one form. This is where that is
 * settled, which is why bbox is the one kind whose mapping needs the view: the
 * media dimensions are the divisor.
 */
function toGeometry(row: BBoxRow, view: ViewInfo): CoordsNorm | null {
  if (!Array.isArray(row.coords) || row.coords.length !== 4) return null;

  // In xyxy the last two slots are the far corner, not a size.
  const [x, y, third, fourth] = row.coords;
  const w = row.format === "xyxy" ? third - x : third;
  const h = row.format === "xyxy" ? fourth - y : fourth;

  const iw = view.width || 1;
  const ih = view.height || 1;
  return row.is_normalized ? [x, y, w, h] : [x / iw, y / ih, w / iw, h / ih];
}

/**
 * The column of a box's row that holds a model's score, as the backend's
 * `BBox` schema declares it: the review reads the score from it.
 */
const BBOX_SCORE_FIELDS: readonly string[] = ["confidence"];

/** REST→local mapping for 2D boxes, normalized to xywh in [0, 1]. */
export const bboxSeedLoader = createViewScopedSeedLoader<"bbox", BBoxRow>({
  kind: "bbox",
  resource: BBOX_RESOURCE,
  toGeometry,
  scoreFields: BBOX_SCORE_FIELDS,
});
