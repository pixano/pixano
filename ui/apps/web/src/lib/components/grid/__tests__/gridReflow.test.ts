/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { GridStack } from "gridstack";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fillGapAndSync, placeWidget, syncLayouts, type LayoutSink } from "../gridReflow.js";
import type { WidgetLayout } from "$lib/extensions/types.js";

// GridStack drives real cell math (positions, collisions, compaction) headlessly
// under happy-dom, so these exercise the actual reflow rather than a re-mock.

let grid: GridStack;
let root: HTMLElement;

function makeSink() {
  const layouts = new Map<string, WidgetLayout>();
  const updateLayout = vi.fn((id: string, layout: Partial<WidgetLayout>) => {
    layouts.set(id, { ...(layouts.get(id) ?? ({} as WidgetLayout)), ...layout });
  });
  const sink: LayoutSink = { updateLayout };
  return { sink, layouts, updateLayout };
}

/** Create a bare grid-item element (stands in for a mounted WidgetFrame). */
function addElement(id: string): HTMLElement {
  const el = document.createElement("div");
  el.dataset.widgetId = id;
  grid.el.appendChild(el);
  return el;
}

function place(id: string, layout: WidgetLayout, sink: LayoutSink) {
  return placeWidget(grid, addElement(id), id, layout, 1, 1, sink);
}

function nodeOf(id: string) {
  const el = grid.getGridItems().find((i) => i.dataset.widgetId === id);
  return el?.gridstackNode;
}

beforeEach(() => {
  root = document.createElement("div");
  root.className = "grid-stack";
  document.body.appendChild(root);
  grid = GridStack.init({ column: 12, cellHeight: 50, float: true }, root);
});

afterEach(() => {
  grid.destroy(false);
  root.remove();
});

describe("placeWidget", () => {
  it("keeps the stored position when the spot is free, and persists it", () => {
    const { sink, layouts } = makeSink();
    place("a", { x: 3, y: 2, w: 3, h: 2 }, sink);
    expect(nodeOf("a")).toMatchObject({ x: 3, y: 2, w: 3, h: 2 });
    // The resolved position is written back unconditionally (grid = source of
    // truth); here it matches the stored spot since it was free.
    expect(layouts.get("a")).toMatchObject({ x: 3, y: 2, w: 3, h: 2 });
  });

  it("drops into the next free spot (same size) when the stored spot is taken", () => {
    const { sink, layouts } = makeSink();
    place("a", { x: 0, y: 0, w: 3, h: 2 }, sink);
    // "b" wants the same slot as "a"; it must land elsewhere without shrinking.
    place("b", { x: 0, y: 0, w: 3, h: 2 }, sink);

    const b = nodeOf("b")!;
    expect({ w: b.w, h: b.h }).toEqual({ w: 3, h: 2 });
    const overlapsA = b.x! < 3 && b.y! < 2; // "a" occupies x:0-2, y:0-1
    expect(overlapsA).toBe(false);
    // The relocated position was persisted back through the sink.
    expect(layouts.get("b")).toMatchObject({ x: b.x, y: b.y });
  });
});

describe("fillGapAndSync", () => {
  it("pulls widgets up to fill a freed gap and persists the moves", () => {
    const { sink, layouts, updateLayout } = makeSink();
    place("a", { x: 0, y: 0, w: 12, h: 2 }, sink);
    place("b", { x: 0, y: 2, w: 12, h: 2 }, sink);
    updateLayout.mockClear();

    // Hide "a": remove it, then fill the hole.
    const aEl = grid.getGridItems().find((i) => i.dataset.widgetId === "a")!;
    grid.removeWidget(aEl, true);
    fillGapAndSync(grid, sink);

    // "b" moved up into the vacated top row, keeping its size.
    expect(nodeOf("b")).toMatchObject({ x: 0, y: 0, w: 12, h: 2 });
    expect(layouts.get("b")).toMatchObject({ y: 0 });
  });

  it("does not resize widgets while compacting", () => {
    const { sink } = makeSink();
    place("a", { x: 0, y: 0, w: 4, h: 3 }, sink);
    place("b", { x: 4, y: 0, w: 4, h: 6 }, sink);
    const bEl = grid.getGridItems().find((i) => i.dataset.widgetId === "b")!;
    grid.removeWidget(bEl, true);
    fillGapAndSync(grid, sink);
    expect(nodeOf("a")).toMatchObject({ w: 4, h: 3 });
  });
});

describe("syncLayouts", () => {
  it("writes back every current grid item's position", () => {
    const { sink, layouts, updateLayout } = makeSink();
    place("a", { x: 1, y: 1, w: 2, h: 2 }, sink);
    place("b", { x: 4, y: 4, w: 2, h: 2 }, sink);
    updateLayout.mockClear();

    syncLayouts(grid, sink);

    expect(layouts.get("a")).toMatchObject({ x: 1, y: 1, w: 2, h: 2 });
    expect(layouts.get("b")).toMatchObject({ x: 4, y: 4, w: 2, h: 2 });
  });
});
