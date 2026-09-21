/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { describe, expect, it, vi } from "vitest";

import { drawPolygonTool, drawPolylineTool } from "../drawMultiPathTool.js";
import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { LocalMultiPath } from "$lib/annotations/annotationCollection.svelte.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";

// Konva needs a native canvas in node; the tool only builds preview shapes and
// throws them away.
vi.mock("konva", () => {
  class Node {
    destroyed = false;
    add(): void {}
    destroy(): void {
      this.destroyed = true;
    }
  }
  return { default: { Group: Node, Circle: Node, Line: Node, Text: Node } };
});

// ─── Harness ─────────────────────────────────────────────────────────────────

/** Image frame at the origin sized 100×100, so pixel == percent in assertions. */
function fakeImage(): Konva.Image {
  return {
    x: () => 0,
    y: () => 0,
    width: () => 100,
    height: () => 100,
  } as unknown as Konva.Image;
}

function makeHarness(opts: { image?: Konva.Image | null } = {}) {
  const collection = new AnnotationCollection();
  let pointer: { x: number; y: number } | null = null;
  const spies = {
    setActiveTool: vi.fn(),
    requestRedraw: vi.fn(),
    beginPendingAnnotation: vi.fn(),
  };
  const ctx: Scene2DContext = {
    widgetId: "w1",
    buildContext: { datasetId: "ds", recordId: "rec", viewId: "view-1" },
    collection,
    mutations: {
      pending: [],
      queue: vi.fn(),
      upsertUpdate: vi.fn(),
      patchPendingCreate: vi.fn(),
      dropForLocalAnnotation: vi.fn(),
      dropPendingEntityCreate: vi.fn(),
    },
    liveDraft: { get: () => null },
    stage: { getPointerPosition: () => pointer } as unknown as Konva.Stage,
    annotationLayer: { add: vi.fn(), batchDraw: vi.fn() } as unknown as Konva.Layer,
    camera: { imageWidth: 100, imageHeight: 100, calibration: null },
    getKonvaImage: () => ("image" in opts ? (opts.image ?? null) : fakeImage()),
    ...spies,
    findEntity: vi.fn(),
    isEntityVisible: () => true,
  };
  return {
    ctx,
    collection,
    spies,
    setPointer: (p: { x: number; y: number } | null) => (pointer = p),
  };
}

type Handler = ReturnType<typeof drawPolygonTool.createHandler>;
type PointerEvt = Parameters<NonNullable<Handler["onPointerDown"]>>[0];

const evt = () => ({ cancelBubble: false }) as PointerEvt;
const key = (k: string) => new KeyboardEvent("keydown", { key: k });

function click(
  handler: Handler,
  setPointer: (p: { x: number; y: number }) => void,
  points: { x: number; y: number }[],
): void {
  for (const p of points) {
    setPointer(p);
    handler.onPointerDown?.(evt());
  }
}

const TRIANGLE = [
  { x: 10, y: 10 },
  { x: 40, y: 10 },
  { x: 40, y: 40 },
];

const firstPath = (collection: AnnotationCollection): LocalMultiPath =>
  collection.byKind("multi_path")[0] as LocalMultiPath;

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("multi-path tool metadata", () => {
  it("exposes two tools over the same kind", () => {
    // Polygon and polyline differ by a geometry flag, not by kind — the backend
    // makes the same choice with `is_closed`.
    expect(drawPolygonTool.kind).toBe("multi_path");
    expect(drawPolylineTool.kind).toBe("multi_path");
    expect(drawPolygonTool.id).not.toBe(drawPolylineTool.id);
  });
});

describe("polygon drawing", () => {
  it("commits a closed ring on Enter", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawPolygonTool.createHandler(ctx);
    handler.activate?.();

    click(handler, setPointer, TRIANGLE);
    handler.onKeyDown?.(key("Enter"));

    const path = firstPath(collection);
    expect(path.geometry).toEqual({
      coords: [0.1, 0.1, 0.4, 0.1, 0.4, 0.4],
      numPoints: [3],
      isClosed: true,
    });
    expect(path.persisted).toBe(false);
  });

  it("does not repeat the first point to close the ring", () => {
    // The backend stores rings open; Konva closes them at render time. Adding a
    // duplicate here would grow the ring by one point on every save.
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawPolygonTool.createHandler(ctx);

    click(handler, setPointer, TRIANGLE);
    handler.onKeyDown?.(key("Enter"));

    expect(firstPath(collection).geometry.numPoints).toEqual([3]);
  });

  it("refuses to commit a ring with fewer than three points", () => {
    const { ctx, collection, spies, setPointer } = makeHarness();
    const handler = drawPolygonTool.createHandler(ctx);

    click(handler, setPointer, TRIANGLE.slice(0, 2));
    handler.onKeyDown?.(key("Enter"));

    expect(collection.byKind("multi_path")).toHaveLength(0);
    expect(spies.beginPendingAnnotation).not.toHaveBeenCalled();
  });

  it("asks for an entity and hands control back to select", () => {
    const { ctx, spies, setPointer } = makeHarness();
    const handler = drawPolygonTool.createHandler(ctx);

    click(handler, setPointer, TRIANGLE);
    handler.onKeyDown?.(key("Enter"));

    expect(spies.beginPendingAnnotation).toHaveBeenCalledTimes(1);
    expect(spies.setActiveTool).toHaveBeenCalledWith("select");
  });
});

describe("polyline drawing", () => {
  it("commits an open path of two points", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawPolylineTool.createHandler(ctx);

    click(handler, setPointer, TRIANGLE.slice(0, 2));
    handler.onKeyDown?.(key("Enter"));

    expect(firstPath(collection).geometry).toEqual({
      coords: [0.1, 0.1, 0.4, 0.1],
      numPoints: [2],
      isClosed: false,
    });
  });

  it("refuses to commit a single point", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawPolylineTool.createHandler(ctx);

    click(handler, setPointer, TRIANGLE.slice(0, 1));
    handler.onKeyDown?.(key("Enter"));

    expect(collection.byKind("multi_path")).toHaveLength(0);
  });
});

describe("sub-paths", () => {
  it("records several parts in one annotation via N", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawPolygonTool.createHandler(ctx);

    click(handler, setPointer, TRIANGLE);
    handler.onKeyDown?.(key("n"));
    click(handler, setPointer, [
      { x: 60, y: 60 },
      { x: 80, y: 60 },
      { x: 70, y: 90 },
    ]);
    handler.onKeyDown?.(key("Enter"));

    const geometry = firstPath(collection).geometry;
    expect(geometry.numPoints).toEqual([3, 3]);
    expect(geometry.coords).toHaveLength(12);
  });

  it("refuses to start a part while the current one is too short", () => {
    // Otherwise the commit would silently drop the points already placed.
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawPolygonTool.createHandler(ctx);

    click(handler, setPointer, TRIANGLE.slice(0, 2));
    handler.onKeyDown?.(key("n"));
    click(handler, setPointer, [TRIANGLE[2]]);
    handler.onKeyDown?.(key("Enter"));

    // The three points stayed in one sub-path rather than being split.
    expect(firstPath(collection).geometry.numPoints).toEqual([3]);
  });

  it("drops a trailing part that never got enough points", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawPolygonTool.createHandler(ctx);

    click(handler, setPointer, TRIANGLE);
    handler.onKeyDown?.(key("n"));
    click(handler, setPointer, [{ x: 60, y: 60 }]);
    handler.onKeyDown?.(key("Enter"));

    expect(firstPath(collection).geometry.numPoints).toEqual([3]);
  });
});

describe("multi-path keyboard", () => {
  it("undoes the last point on Backspace", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawPolygonTool.createHandler(ctx);

    click(handler, setPointer, [...TRIANGLE, { x: 90, y: 90 }]);
    handler.onKeyDown?.(key("Backspace"));
    handler.onKeyDown?.(key("Enter"));

    expect(firstPath(collection).geometry.coords).toEqual([0.1, 0.1, 0.4, 0.1, 0.4, 0.4]);
  });

  it("steps back into the previous part when the current one is empty", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawPolygonTool.createHandler(ctx);

    click(handler, setPointer, TRIANGLE);
    handler.onKeyDown?.(key("n"));
    handler.onKeyDown?.(key("Backspace"));
    click(handler, setPointer, [{ x: 90, y: 90 }]);
    handler.onKeyDown?.(key("Enter"));

    // Back to one part, whose last point was replaced.
    expect(firstPath(collection).geometry.numPoints).toEqual([3]);
    expect(firstPath(collection).geometry.coords.slice(-2)).toEqual([0.9, 0.9]);
  });

  it("clamps a click outside the image, which the backend would reject", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawPolygonTool.createHandler(ctx);

    click(handler, setPointer, [
      { x: -40, y: -40 },
      { x: 200, y: 200 },
      { x: 40, y: 40 },
    ]);
    handler.onKeyDown?.(key("Enter"));

    const coords = firstPath(collection).geometry.coords;
    expect(coords.every((c) => c >= 0 && c <= 1)).toBe(true);
    expect(coords.slice(0, 4)).toEqual([0, 0, 1, 1]);
  });

  it("discards the path on Escape", () => {
    const { ctx, collection, spies, setPointer } = makeHarness();
    const handler = drawPolygonTool.createHandler(ctx);

    click(handler, setPointer, TRIANGLE);
    handler.onKeyDown?.(key("Escape"));

    expect(collection.byKind("multi_path")).toHaveLength(0);
    expect(spies.setActiveTool).toHaveBeenCalledWith("select");
  });

  it("starts fresh after a commit", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawPolygonTool.createHandler(ctx);

    click(handler, setPointer, TRIANGLE);
    handler.onKeyDown?.(key("Enter"));
    click(handler, setPointer, TRIANGLE);
    handler.onKeyDown?.(key("Enter"));

    expect(collection.byKind("multi_path")).toHaveLength(2);
  });

  it("places nothing when the image frame is unavailable", () => {
    const { ctx, collection, setPointer } = makeHarness({ image: null });
    const handler = drawPolygonTool.createHandler(ctx);

    click(handler, setPointer, TRIANGLE);
    handler.onKeyDown?.(key("Enter"));

    expect(collection.byKind("multi_path")).toHaveLength(0);
  });

  it("reports which keys it consumed", () => {
    const { ctx } = makeHarness();
    const handler = drawPolygonTool.createHandler(ctx);

    for (const k of ["Escape", "Enter", "n", "Backspace"]) {
      expect(handler.onKeyDown?.(key(k))).toBe(true);
    }
    expect(handler.onKeyDown?.(key("a"))).toBe(false);
  });
});
