/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  SELECTED_OPACITY_BOOST,
  SELECTED_STROKE_SCALE,
  VERTEX_HIT_RADIUS,
} from "$lib/annotations/scene/scene2dGeometry.js";

/**
 * These three constants are the whole of the shared selection language, so the
 * properties that make them work are asserted here rather than re-derived in
 * each kind's renderer test.
 */
describe("2D selection styling", () => {
  it("makes a vertex easier to hit than it is to see", () => {
    // Every kind draws its handles at radius 4; a target smaller than the dot
    // would defeat the point, and a miss falls through to the stage and
    // deselects, which reads as "the tool is broken".
    const DRAWN_VERTEX_RADIUS = 4;
    expect(VERTEX_HIT_RADIUS).toBeGreaterThan(DRAWN_VERTEX_RADIUS);
  });

  it("gives a selected outline a visible weight, not a subtle one", () => {
    expect(SELECTED_STROKE_SCALE).toBeGreaterThan(1);
  });

  it("keeps a boosted mask translucent enough to see the media through it", () => {
    // The mask kind tints at 0.45 and adds this on selection; going opaque
    // would hide the pixels the annotator is checking their work against.
    const MASK_OPACITY = 0.45;
    expect(SELECTED_OPACITY_BOOST).toBeGreaterThan(0);
    expect(MASK_OPACITY + SELECTED_OPACITY_BOOST).toBeLessThan(1);
  });
});
