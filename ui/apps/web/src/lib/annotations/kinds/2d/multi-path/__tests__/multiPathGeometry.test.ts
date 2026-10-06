/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { fromNormalizedSubPaths, toPixelSubPaths } from "../multiPathGeometry";
import type { MultiPathGeometry } from "../multiPathTypes";

/** Frame at the origin sized 100×100, so pixel == percent in assertions. */
const FRAME = { x: 0, y: 0, w: 100, h: 100 };

describe("toPixelSubPaths", () => {
  it("slices the flat coord list at the offsets num_points declares", () => {
    const geometry: MultiPathGeometry = {
      coords: [0, 0, 0.5, 0, 0.5, 0.5, 0.8, 0.8, 0.9, 0.9],
      numPoints: [3, 2],
      isClosed: false,
    };

    expect(toPixelSubPaths(geometry, FRAME)).toEqual([
      [0, 0, 50, 0, 50, 50],
      [80, 80, 90, 90],
    ]);
  });

  it("offsets and scales by the frame", () => {
    const geometry: MultiPathGeometry = {
      coords: [0, 0, 1, 1],
      numPoints: [2],
      isClosed: false,
    };

    expect(toPixelSubPaths(geometry, { x: 10, y: 20, w: 200, h: 400 })).toEqual([
      [10, 20, 210, 420],
    ]);
  });

  it("stops rather than inventing a sub-path when num_points overruns the coords", () => {
    // The seed loader rejects such rows, so reaching this means a tool built
    // one — drawing a guessed shape would hide that bug.
    const geometry: MultiPathGeometry = {
      coords: [0, 0, 0.5, 0.5],
      numPoints: [2, 3],
      isClosed: false,
    };

    expect(toPixelSubPaths(geometry, FRAME)).toEqual([[0, 0, 50, 50]]);
  });
});

describe("fromNormalizedSubPaths", () => {
  it("concatenates the points and records each sub-path's length", () => {
    const geometry = fromNormalizedSubPaths(
      [
        [
          { x: 0, y: 0 },
          { x: 0.5, y: 0 },
          { x: 0.5, y: 0.5 },
        ],
        [
          { x: 0.8, y: 0.8 },
          { x: 0.9, y: 0.9 },
        ],
      ],
      true,
    );

    expect(geometry.coords).toEqual([0, 0, 0.5, 0, 0.5, 0.5, 0.8, 0.8, 0.9, 0.9]);
    expect(geometry.numPoints).toEqual([3, 2]);
    expect(geometry.isClosed).toBe(true);
  });

  it("skips empty sub-paths so num_points never records a zero", () => {
    const geometry = fromNormalizedSubPaths([[{ x: 0, y: 0 }], [], [{ x: 1, y: 1 }]], false);
    expect(geometry.numPoints).toEqual([1, 1]);
  });

  it("round-trips through toPixelSubPaths", () => {
    const subPaths = [
      [
        { x: 0.1, y: 0.1 },
        { x: 0.4, y: 0.1 },
        { x: 0.4, y: 0.4 },
      ],
      [
        { x: 0.6, y: 0.6 },
        { x: 0.9, y: 0.9 },
      ],
    ];
    const geometry = fromNormalizedSubPaths(subPaths, true);

    expect(toPixelSubPaths(geometry, FRAME)).toEqual([
      [10, 10, 40, 10, 40, 40],
      [60, 60, 90, 90],
    ]);
  });
});
