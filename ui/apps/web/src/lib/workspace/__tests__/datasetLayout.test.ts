/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  DATASET_LAYOUT_VERSION,
  parseDatasetLayout,
  resolveRecordLayouts,
  snapshotDatasetLayout,
  toDatasetLayout,
  type DatasetLayout,
} from "../datasetLayout.js";
import { planViewportLayouts } from "../layoutPlanner.js";
import type { WidgetInstance } from "$lib/extensions/types.js";

const VIEWPORT = { width: 1600, height: 900 };

function makeWidget(overrides: Partial<WidgetInstance>): WidgetInstance {
  return {
    id: "w-1",
    extensionName: "image",
    title: "Widget",
    layout: { x: 0, y: 0, w: 6, h: 4 },
    options: {},
    ...overrides,
  };
}

function makeStoredLayout(views: DatasetLayout["views"]): DatasetLayout {
  return { version: DATASET_LAYOUT_VERSION, views };
}

// ─── snapshotDatasetLayout ───────────────────────────────────────────────────

describe("snapshotDatasetLayout", () => {
  it("captures view-backed widgets keyed by their view name", () => {
    const snapshot = snapshotDatasetLayout([
      makeWidget({ id: "w-1", viewName: "cam", layout: { x: 0, y: 0, w: 6, h: 4 } }),
      makeWidget({ id: "w-2", viewName: "lidar", layout: { x: 6, y: 0, w: 6, h: 4 } }),
    ]);

    expect(snapshot).toEqual({
      version: DATASET_LAYOUT_VERSION,
      views: {
        cam: { layout: { x: 0, y: 0, w: 6, h: 4 }, hidden: false },
        lidar: { layout: { x: 6, y: 0, w: 6, h: 4 }, hidden: false },
      },
    });
  });

  it("records the hidden flag so a hidden view stays hidden on the next record", () => {
    const snapshot = snapshotDatasetLayout([
      makeWidget({ id: "w-1", viewName: "cam", hidden: true }),
      makeWidget({ id: "w-2", viewName: "lidar" }),
    ]);

    expect(snapshot?.views.cam.hidden).toBe(true);
    expect(snapshot?.views.lidar.hidden).toBe(false);
  });

  it("refuses to remember a fully hidden workspace, which would open blank", () => {
    const snapshot = snapshotDatasetLayout([
      makeWidget({ id: "w-1", viewName: "cam", hidden: true }),
      makeWidget({ id: "w-2", viewName: "lidar", hidden: true }),
    ]);

    expect(snapshot).toBeNull();
  });

  it("copies the layout so later widget moves do not mutate the snapshot", () => {
    const widget = makeWidget({ viewName: "cam" });
    const snapshot = snapshotDatasetLayout([widget]);

    widget.layout.x = 9;

    expect(snapshot?.views.cam.layout.x).toBe(0);
  });

  it("skips palette widgets, which no other record has a counterpart for", () => {
    const snapshot = snapshotDatasetLayout([
      makeWidget({ id: "w-1", viewName: "cam" }),
      makeWidget({ id: "w-2", extensionName: "text" }),
    ]);

    expect(Object.keys(snapshot?.views ?? {})).toEqual(["cam"]);
  });

  it("returns null when nothing is capturable, so callers do not erase what is stored", () => {
    expect(snapshotDatasetLayout([])).toBeNull();
    expect(snapshotDatasetLayout([makeWidget({ extensionName: "text" })])).toBeNull();
  });
});

// ─── resolveRecordLayouts ────────────────────────────────────────────────────

describe("resolveRecordLayouts", () => {
  it("replays the stored arrangement for views the user arranged", () => {
    const saved = makeStoredLayout({
      cam: { layout: { x: 3, y: 6, w: 9, h: 5 }, hidden: false },
      lidar: { layout: { x: 0, y: 0, w: 3, h: 5 }, hidden: true },
    });

    expect(resolveRecordLayouts(["cam", "lidar"], VIEWPORT, saved)).toEqual([
      { layout: { x: 3, y: 6, w: 9, h: 5 }, hidden: false },
      { layout: { x: 0, y: 0, w: 3, h: 5 }, hidden: true },
    ]);
  });

  it("falls back to automatic placement when nothing is stored", () => {
    const planned = planViewportLayouts(3, VIEWPORT);

    expect(resolveRecordLayouts(["a", "b", "c"], VIEWPORT, null)).toEqual(
      planned.map((layout) => ({ layout, hidden: false })),
    );
  });

  it("mixes stored and automatic placement when a record has an unarranged view", () => {
    const saved = makeStoredLayout({ cam: { layout: { x: 3, y: 6, w: 9, h: 5 }, hidden: false } });
    const planned = planViewportLayouts(2, VIEWPORT);

    expect(resolveRecordLayouts(["cam", "lidar"], VIEWPORT, saved)).toEqual([
      { layout: { x: 3, y: 6, w: 9, h: 5 }, hidden: false },
      { layout: planned[1], hidden: false },
    ]);
  });

  it("ignores stored views the record does not have", () => {
    const saved = makeStoredLayout({
      cam: { layout: { x: 3, y: 6, w: 9, h: 5 }, hidden: false },
      gone: { layout: { x: 0, y: 0, w: 1, h: 1 }, hidden: false },
    });

    expect(resolveRecordLayouts(["cam"], VIEWPORT, saved)).toHaveLength(1);
  });

  it("copies stored layouts so moving a widget does not rewrite the preference", () => {
    const saved = makeStoredLayout({ cam: { layout: { x: 3, y: 6, w: 9, h: 5 }, hidden: false } });

    const [resolved] = resolveRecordLayouts(["cam"], VIEWPORT, saved);
    resolved.layout.x = 0;

    expect(saved.views.cam.layout.x).toBe(3);
  });

  it("returns nothing for a record with no renderable view", () => {
    expect(resolveRecordLayouts([], VIEWPORT, null)).toEqual([]);
  });
});

// ─── toDatasetLayout ─────────────────────────────────────────────────────────

describe("toDatasetLayout", () => {
  it("expresses a record's resolved placement as a replayable arrangement", () => {
    const layout = toDatasetLayout(
      ["cam", "lidar"],
      [
        { layout: { x: 0, y: 0, w: 6, h: 4 }, hidden: false },
        { layout: { x: 6, y: 0, w: 6, h: 4 }, hidden: true },
      ],
    );

    expect(layout).toEqual({
      version: DATASET_LAYOUT_VERSION,
      views: {
        cam: { layout: { x: 0, y: 0, w: 6, h: 4 }, hidden: false },
        lidar: { layout: { x: 6, y: 0, w: 6, h: 4 }, hidden: true },
      },
    });
  });

  it("copies layouts so later moves cannot rewrite the opening arrangement", () => {
    const resolved = [{ layout: { x: 0, y: 0, w: 6, h: 4 }, hidden: false }];
    const layout = toDatasetLayout(["cam"], resolved);

    resolved[0].layout.x = 9;

    expect(layout.views.cam.layout.x).toBe(0);
  });

  it("round-trips through resolveRecordLayouts", () => {
    const resolved = resolveRecordLayouts(["cam", "lidar"], VIEWPORT, null);

    expect(
      resolveRecordLayouts(["cam", "lidar"], VIEWPORT, toDatasetLayout(["cam", "lidar"], resolved)),
    ).toEqual(resolved);
  });
});

// ─── parseDatasetLayout ──────────────────────────────────────────────────────

describe("parseDatasetLayout", () => {
  it("accepts a well-formed payload", () => {
    const stored = makeStoredLayout({ cam: { layout: { x: 1, y: 2, w: 3, h: 4 }, hidden: true } });

    expect(parseDatasetLayout(JSON.parse(JSON.stringify(stored)))).toEqual(stored);
  });

  it("defaults a missing hidden flag to visible", () => {
    const parsed = parseDatasetLayout({
      version: DATASET_LAYOUT_VERSION,
      views: { cam: { layout: { x: 1, y: 2, w: 3, h: 4 } } },
    });

    expect(parsed?.views.cam.hidden).toBe(false);
  });

  it("discards a payload written by another shape version", () => {
    expect(
      parseDatasetLayout({
        version: DATASET_LAYOUT_VERSION + 1,
        views: { cam: { layout: { x: 1, y: 2, w: 3, h: 4 }, hidden: false } },
      }),
    ).toBeNull();
  });

  it("drops only the unreadable views, keeping the usable ones", () => {
    const parsed = parseDatasetLayout({
      version: DATASET_LAYOUT_VERSION,
      views: {
        cam: { layout: { x: 1, y: 2, w: 3, h: 4 }, hidden: false },
        broken: { layout: { x: "1", y: 2, w: 3, h: 4 } },
        missing: {},
      },
    });

    expect(Object.keys(parsed?.views ?? {})).toEqual(["cam"]);
  });

  it.each([
    ["non-finite", { x: Number.NaN, y: 0, w: 3, h: 4 }],
    ["fractional", { x: 0.5, y: 0, w: 3, h: 4 }],
    ["fractional span", { x: 0, y: 0, w: 2.5, h: 4 }],
    ["negative offset", { x: -1, y: 0, w: 3, h: 4 }],
    ["zero-width", { x: 0, y: 0, w: 0, h: 4 }],
    ["past the last column", { x: 10, y: 0, w: 4, h: 4 }],
  ])("rejects a %s cell, which GridStack could not honour", (_label, layout) => {
    expect(
      parseDatasetLayout({ version: DATASET_LAYOUT_VERSION, views: { cam: { layout } } }),
    ).toBeNull();
  });

  it("keeps a widget taller than the grid is wide (rows are unbounded)", () => {
    const parsed = parseDatasetLayout({
      version: DATASET_LAYOUT_VERSION,
      views: { cam: { layout: { x: 0, y: 0, w: 12, h: 20 } } },
    });

    expect(parsed?.views.cam.layout.h).toBe(20);
  });

  it("rejects payloads that are not a layout at all", () => {
    expect(parseDatasetLayout(null)).toBeNull();
    expect(parseDatasetLayout("nope")).toBeNull();
    expect(parseDatasetLayout([])).toBeNull();
    expect(parseDatasetLayout({ version: DATASET_LAYOUT_VERSION })).toBeNull();
    expect(parseDatasetLayout({ version: DATASET_LAYOUT_VERSION, views: {} })).toBeNull();
  });
});
