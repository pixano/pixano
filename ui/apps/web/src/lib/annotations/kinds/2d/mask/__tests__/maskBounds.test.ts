/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { maskBounds } from "../maskRaster.js";

// A 4-row × 3-column grid, counts alternating background/foreground from index
// 0, laid out column by column as the backend stores them.
const SIZE: [number, number] = [4, 3];

describe("maskBounds", () => {
  it("finds a single painted pixel", () => {
    // 5 background, then 1 painted at index 5 → column 1, row 1.
    expect(maskBounds([5, 1], SIZE)).toEqual({ x: 1, y: 1, width: 1, height: 1 });
  });

  it("spans the rows a run covers inside one column", () => {
    // Painted indices 4..6 → column 1, rows 0..2.
    expect(maskBounds([4, 3], SIZE)).toEqual({ x: 1, y: 0, width: 1, height: 3 });
  });

  it("covers every row when a run crosses a column boundary", () => {
    // Indices 2..9 straddle columns 0, 1 and 2, so no row is left out.
    expect(maskBounds([2, 8], SIZE)).toEqual({ x: 0, y: 0, width: 3, height: 4 });
  });

  it("merges separate runs into one box", () => {
    // One pixel at index 0 (col 0, row 0), another at index 11 (col 2, row 3).
    expect(maskBounds([0, 1, 10, 1], SIZE)).toEqual({ x: 0, y: 0, width: 3, height: 4 });
  });

  it("returns null for a mask with nothing painted", () => {
    expect(maskBounds([12], SIZE)).toBeNull();
  });

  it("returns null for a degenerate grid", () => {
    expect(maskBounds([1], [0, 0])).toBeNull();
  });
});
