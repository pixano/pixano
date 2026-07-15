/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  GRID_MAX_COLS,
  GRID_MIN_CELL,
  GRID_TOTAL_COLS,
  measureGridViewport,
  pickRenderableViews,
  planViewportLayouts,
} from "../layoutPlanner.js";

// ─── Constants ───────────────────────────────────────────────────────────────

describe("exported constants", () => {
  it("GRID_TOTAL_COLS is 12", () => expect(GRID_TOTAL_COLS).toBe(12));
  it("GRID_MIN_CELL is 3", () => expect(GRID_MIN_CELL).toBe(3));
  it("GRID_MAX_COLS is floor(12/3) = 4", () => expect(GRID_MAX_COLS).toBe(4));
});

// ─── pickRenderableViews ──────────────────────────────────────────────────────

describe("pickRenderableViews", () => {
  const views = {
    cam_front: { base: "Image" },
    lidar: { base: "PointCloud" },
    cam_back: { base: "Image" },
    depth: { base: "DepthMap" },
    text_field: { base: undefined as unknown as string },
  };

  it("keeps only entries whose base satisfies the predicate", () => {
    const result = pickRenderableViews(views, (b) => b === "Image");
    expect(result.map(([k]) => k)).toEqual(["cam_front", "cam_back"]);
  });

  it("returns entries in insertion order", () => {
    const result = pickRenderableViews(views, (b) => b === "Image" || b === "PointCloud");
    expect(result.map(([k]) => k)).toEqual(["cam_front", "lidar", "cam_back"]);
  });

  it("returns [] when views is undefined", () => {
    expect(pickRenderableViews(undefined, () => true)).toEqual([]);
  });

  it("returns [] when no entry passes the predicate", () => {
    expect(pickRenderableViews(views, () => false)).toEqual([]);
  });

  it("excludes entries with no base (falsy)", () => {
    const result = pickRenderableViews(views, () => true);
    expect(result.map(([k]) => k)).not.toContain("text_field");
  });
});

// ─── planViewportLayouts ──────────────────────────────────────────────────────

describe("planViewportLayouts", () => {
  it("returns empty array for count <= 0", () => {
    expect(planViewportLayouts(0, { width: 1600, height: 900 })).toEqual([]);
    expect(planViewportLayouts(-1, { width: 1600, height: 900 })).toEqual([]);
  });

  it("single widget fills first cell", () => {
    const [layout] = planViewportLayouts(1, { width: 1200, height: 900 });
    expect(layout).toMatchObject({ x: 0, y: 0 });
    expect(layout.w).toBeGreaterThanOrEqual(GRID_MIN_CELL);
    expect(layout.h).toBeGreaterThanOrEqual(GRID_MIN_CELL);
  });

  it("all layouts have w,h >= GRID_MIN_CELL", () => {
    for (const count of [1, 2, 3, 4, 6, 9]) {
      const layouts = planViewportLayouts(count, { width: 1600, height: 900 });
      for (const l of layouts) {
        expect(l.w).toBeGreaterThanOrEqual(GRID_MIN_CELL);
        expect(l.h).toBeGreaterThanOrEqual(GRID_MIN_CELL);
      }
    }
  });

  it("returns exactly count layouts", () => {
    for (const count of [1, 2, 4, 7]) {
      expect(planViewportLayouts(count, { width: 1600, height: 900 })).toHaveLength(count);
    }
  });

  it("no layout x + w exceeds GRID_TOTAL_COLS", () => {
    const layouts = planViewportLayouts(4, { width: 1600, height: 900 });
    for (const l of layouts) {
      expect(l.x + l.w).toBeLessThanOrEqual(GRID_TOTAL_COLS);
    }
  });

  it("cols <= GRID_MAX_COLS for any count", () => {
    // 9 widgets in a 2-col forced layout
    const layouts = planViewportLayouts(9, { width: 1600, height: 900 });
    const maxX = Math.max(...layouts.map((l) => l.x));
    expect(maxX).toBeLessThan(GRID_TOTAL_COLS);
  });

  it("adjacent widgets in a row don't overlap", () => {
    const layouts = planViewportLayouts(2, { width: 1600, height: 900 });
    const sorted = [...layouts].sort((a, b) => a.x - b.x);
    if (sorted[0].y === sorted[1].y) {
      expect(sorted[0].x + sorted[0].w).toBeLessThanOrEqual(sorted[1].x);
    }
  });

  it("degrades gracefully for tiny viewport dimensions", () => {
    const layouts = planViewportLayouts(1, { width: 1, height: 1 });
    expect(layouts[0].w).toBeGreaterThanOrEqual(GRID_MIN_CELL);
    expect(layouts[0].h).toBeGreaterThanOrEqual(GRID_MIN_CELL);
  });
});

// ─── measureGridViewport ──────────────────────────────────────────────────────

describe("measureGridViewport", () => {
  it("returns default 1600×900 when document is undefined", () => {
    // happy-dom exposes document, so we stub it away
    const origDoc = globalThis.document;
    // @ts-expect-error intentional undefined override
    globalThis.document = undefined;
    try {
      const vp = measureGridViewport();
      expect(vp).toEqual({ width: 1600, height: 900 });
    } finally {
      globalThis.document = origDoc;
    }
  });

  it("returns 1600×900 fallback when .grid-stack element is absent", () => {
    // happy-dom has a DOM but no .grid-stack element by default
    const vp = measureGridViewport();
    expect(vp.width).toBe(1600);
    expect(vp.height).toBe(900);
  });

  it("reads height from the stable parent, not the grid's overridden height", () => {
    // GridStack rewrites `.grid-stack`'s inline height to its content height
    // (rows × cellHeight). If a widget was enlarged, that grid height grows
    // past the viewport; measuring it would ratchet the next record larger.
    // We must read the parent (fixed viewport wrapper) height instead.
    const parent = document.createElement("div");
    Object.defineProperty(parent, "clientHeight", { value: 900, configurable: true });

    const grid = document.createElement("div");
    grid.className = "grid-stack";
    Object.defineProperty(grid, "clientWidth", { value: 1600, configurable: true });
    // Grown content height, as GridStack would set after a manual enlarge.
    Object.defineProperty(grid, "clientHeight", { value: 4000, configurable: true });

    parent.appendChild(grid);
    document.body.appendChild(parent);
    try {
      const vp = measureGridViewport();
      expect(vp.width).toBe(1600);
      expect(vp.height).toBe(900);
    } finally {
      parent.remove();
    }
  });
});
