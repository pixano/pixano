/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  cutAtImageEdges,
  IMAGE_EDGE_TOLERANCE,
  movedInsideImage,
  type MinimumBoxSize,
} from "../bboxImageBounds.js";
import type { CoordsNorm } from "$lib/annotations/types.js";

/** How close a coordinate computed here lands to what was meant. */
const COORDS_DIGITS = 12;
/** A float's error, as a box let go on an edge comes back from pixels with. */
const FLOAT_NOISE = 8.881784197001253e-18;
/** The least size a box is cut to: a pixel of a 100 × 50 px image. */
const LEAST: MinimumBoxSize = { width: 0.01, height: 0.02 };

function expectCoords(actual: CoordsNorm, expected: CoordsNorm): void {
  actual.forEach((value, index) => expect(value).toBeCloseTo(expected[index], COORDS_DIGITS));
}

/** What the server takes: every coordinate in [0, 1], and the box inside the image. */
function expectInsideTheImage([x, y, w, h]: CoordsNorm): void {
  for (const value of [x, y, w, h]) {
    expect(value).toBeGreaterThanOrEqual(0);
    expect(value).toBeLessThanOrEqual(1);
  }
  expect(x + w).toBeLessThanOrEqual(1);
  expect(y + h).toBeLessThanOrEqual(1);
}

describe("movedInsideImage", () => {
  it("leaves a box inside the image as it is", () => {
    expect(movedInsideImage([0.1, 0.2, 0.3, 0.4])).toEqual([0.1, 0.2, 0.3, 0.4]);
  });

  it.each<[string, CoordsNorm, CoordsNorm]>([
    ["left and top", [-0.15, -0.05, 0.2, 0.2], [0, 0, 0.2, 0.2]],
    ["right and bottom", [0.95, 0.9, 0.2, 0.3], [0.8, 0.7, 0.2, 0.3]],
  ])("stops a box dropped past the %s edges against them, whole", (_, dropped, expected) => {
    const moved = movedInsideImage(dropped);

    expectCoords(moved, expected);
    expectInsideTheImage(moved);
  });

  it("puts on the edge a box a float's error from it, on either side", () => {
    expect(movedInsideImage([-FLOAT_NOISE, FLOAT_NOISE, 0.2, 0.2]).slice(0, 2)).toEqual([0, 0]);
  });
});

describe("cutAtImageEdges", () => {
  it("leaves a box inside the image as it is", () => {
    expectCoords(cutAtImageEdges([0.1, 0.2, 0.3, 0.4], LEAST), [0.1, 0.2, 0.3, 0.4]);
  });

  it.each<[string, CoordsNorm, CoordsNorm]>([
    ["left and top", [-0.15, -0.05, 0.45, 0.35], [0, 0, 0.3, 0.3]],
    ["right and bottom", [0.1, 0.1, 1.0, 1.2], [0.1, 0.1, 0.9, 0.9]],
  ])("cuts a box resized past the %s edges at them", (_, resized, expected) => {
    const cut = cutAtImageEdges(resized, LEAST);

    expectCoords(cut, expected);
    expectInsideTheImage(cut);
  });

  it("puts on the edge an edge a float's error from it, on either side", () => {
    // A handle let go on the left edge, a hair past it or short of it.
    expect(cutAtImageEdges([-FLOAT_NOISE, 0.1, 0.1, 0.2], LEAST)[0]).toBe(0);
    expect(cutAtImageEdges([FLOAT_NOISE, 0.1, 0.1, 0.2], LEAST)[0]).toBe(0);
    // One let go on the right edge, a hair short of it: the box reaches it.
    const [x, , w] = cutAtImageEdges([0.3, 0.1, 0.7 - IMAGE_EDGE_TOLERANCE / 2, 0.2], LEAST);
    expect(x + w).toBe(1);
  });

  it("keeps an edge further from the image's edge than the tolerance where it is", () => {
    const nearTheEdge = 2 * IMAGE_EDGE_TOLERANCE;

    expect(cutAtImageEdges([nearTheEdge, 0.1, 0.1, 0.2], LEAST)[0]).toBe(nearTheEdge);
  });

  // A box resized to lie wholly past an edge — it lay on that edge, and its
  // other handle was taken past it — or all but a sliver of it.
  it.each<[string, CoordsNorm, CoordsNorm]>([
    ["wholly past the left edge", [-0.2, 0.1, 0.2, 0.2], [0, 0.1, 0.01, 0.2]],
    ["wholly past the right edge", [1, 0.1, 0.4, 0.2], [0.99, 0.1, 0.01, 0.2]],
    ["wholly past the top edge", [0.1, -0.3, 0.2, 0.3], [0.1, 0, 0.2, 0.02]],
    ["wholly past the bottom edge", [0.1, 1, 0.2, 0.3], [0.1, 0.98, 0.2, 0.02]],
    ["past the left edge but for a sliver", [-0.2, 0.1, 0.205, 0.2], [0, 0.1, 0.01, 0.2]],
    ["past the right edge but for a sliver", [0.995, 0.1, 0.4, 0.2], [0.99, 0.1, 0.01, 0.2]],
  ])("keeps a box resized %s at the least size, against that edge", (_, resized, expected) => {
    const cut = cutAtImageEdges(resized, LEAST);

    expectCoords(cut, expected);
    expectInsideTheImage(cut);
  });

  it("keeps a box as large as an image smaller than the least size", () => {
    const cut = cutAtImageEdges([-0.5, 1.5, 0.5, 0.5], { width: 2, height: 3 });

    expectCoords(cut, [0, 0, 1, 1]);
    expectInsideTheImage(cut);
  });
});
