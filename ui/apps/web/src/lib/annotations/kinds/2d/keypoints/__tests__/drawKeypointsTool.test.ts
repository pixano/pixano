/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { describe, expect, it, vi } from "vitest";

import { drawKeypointsTool } from "../drawKeypointsTool.js";
import { DEFAULT_KEYPOINT_TEMPLATE, KEYPOINT_TEMPLATES } from "../keypointsTemplates.js";
import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";

// Konva needs a native canvas in node; the tool only builds preview shapes and
// throws them away. Mock the three node types it constructs.
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

type PointerEvt = Parameters<
  NonNullable<ReturnType<typeof drawKeypointsTool.createHandler>["onPointerDown"]>
>[0];

const evt = () => ({ cancelBubble: false }) as PointerEvt;

/** Click each point in turn. */
function placePoints(
  handler: ReturnType<typeof drawKeypointsTool.createHandler>,
  setPointer: (p: { x: number; y: number }) => void,
  points: { x: number; y: number }[],
): void {
  for (const p of points) {
    setPointer(p);
    handler.onPointerDown?.(evt());
  }
}

/** Four clicks — the point count of the default (face) template. */
const FACE_CLICKS = [
  { x: 30, y: 25 },
  { x: 60, y: 25 },
  { x: 45, y: 45 },
  { x: 45, y: 75 },
];

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("drawKeypointsTool metadata", () => {
  it("declares the keypoints kind so the toolbar can group it", () => {
    expect(drawKeypointsTool.kind).toBe("keypoints");
    expect(drawKeypointsTool.id).toBe("draw-keypoints");
  });
});

describe("drawKeypointsTool placement", () => {
  it("commits once every template point has been placed", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawKeypointsTool.createHandler(ctx);
    handler.activate?.();

    placePoints(handler, setPointer, FACE_CLICKS);

    const skeletons = collection.byKind("keypoints");
    expect(skeletons).toHaveLength(1);
    expect(skeletons[0].geometry.templateId).toBe(DEFAULT_KEYPOINT_TEMPLATE.id);
    expect(skeletons[0].persisted).toBe(false);
  });

  it("commits nothing before the last point", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawKeypointsTool.createHandler(ctx);

    placePoints(handler, setPointer, FACE_CLICKS.slice(0, 3));

    expect(collection.byKind("keypoints")).toHaveLength(0);
  });

  it("normalizes the clicked positions into [0,1]", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawKeypointsTool.createHandler(ctx);

    placePoints(handler, setPointer, FACE_CLICKS);

    expect(collection.byKind("keypoints")[0].geometry.coords).toEqual([
      0.3, 0.25, 0.6, 0.25, 0.45, 0.45, 0.45, 0.75,
    ]);
  });

  it("clamps a click outside the image, which the backend would reject", () => {
    // `KeyPoints` validates that every coordinate is positive.
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawKeypointsTool.createHandler(ctx);

    placePoints(handler, setPointer, [
      { x: -40, y: -40 },
      { x: 200, y: 200 },
      { x: 45, y: 45 },
      { x: 45, y: 75 },
    ]);

    const coords = collection.byKind("keypoints")[0].geometry.coords;
    expect(coords.every((c) => c >= 0 && c <= 1)).toBe(true);
    expect(coords.slice(0, 4)).toEqual([0, 0, 1, 1]);
  });

  it("emits one state per point, all visible by default", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawKeypointsTool.createHandler(ctx);

    placePoints(handler, setPointer, FACE_CLICKS);

    const { coords, states } = collection.byKind("keypoints")[0].geometry;
    expect(states).toHaveLength(coords.length / 2);
    expect(states).toEqual(["visible", "visible", "visible", "visible"]);
  });

  it("asks for an entity and hands control back to select", () => {
    const { ctx, spies, setPointer } = makeHarness();
    const handler = drawKeypointsTool.createHandler(ctx);

    placePoints(handler, setPointer, FACE_CLICKS);

    expect(spies.beginPendingAnnotation).toHaveBeenCalledTimes(1);
    expect(spies.setActiveTool).toHaveBeenCalledWith("select");
  });

  it("places nothing when the image frame is unavailable", () => {
    const { ctx, collection, setPointer } = makeHarness({ image: null });
    const handler = drawKeypointsTool.createHandler(ctx);

    placePoints(handler, setPointer, FACE_CLICKS);

    expect(collection.byKind("keypoints")).toHaveLength(0);
  });
});

describe("drawKeypointsTool keyboard", () => {
  it("undoes the last point on Backspace", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawKeypointsTool.createHandler(ctx);

    placePoints(handler, setPointer, FACE_CLICKS.slice(0, 3));
    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Backspace" }));
    // Three clicks minus one undo, then two more: the fourth click completes it.
    placePoints(handler, setPointer, [FACE_CLICKS[2], FACE_CLICKS[3]]);

    expect(collection.byKind("keypoints")).toHaveLength(1);
  });

  it("marks the next point occluded with I", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawKeypointsTool.createHandler(ctx);

    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "i" }));
    placePoints(handler, setPointer, FACE_CLICKS);

    // The flag applies to one point only, then resets.
    expect(collection.byKind("keypoints")[0].geometry.states).toEqual([
      "invisible",
      "visible",
      "visible",
      "visible",
    ]);
  });

  it("cycles templates with T before the first point", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawKeypointsTool.createHandler(ctx);

    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "t" }));
    const expected = KEYPOINT_TEMPLATES[1];
    placePoints(
      handler,
      setPointer,
      expected.points.map((_, i) => ({ x: 10 + i, y: 10 + i })),
    );

    expect(collection.byKind("keypoints")[0].geometry.templateId).toBe(expected.id);
  });

  it("refuses to switch template once a point is placed", () => {
    // The placed points are bound to the current template's count and labels.
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawKeypointsTool.createHandler(ctx);

    placePoints(handler, setPointer, [FACE_CLICKS[0]]);
    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "t" }));
    placePoints(handler, setPointer, FACE_CLICKS.slice(1));

    expect(collection.byKind("keypoints")[0].geometry.templateId).toBe(
      DEFAULT_KEYPOINT_TEMPLATE.id,
    );
  });

  it("discards the skeleton on Escape", () => {
    const { ctx, collection, spies, setPointer } = makeHarness();
    const handler = drawKeypointsTool.createHandler(ctx);

    placePoints(handler, setPointer, FACE_CLICKS.slice(0, 2));
    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Escape" }));

    expect(collection.byKind("keypoints")).toHaveLength(0);
    expect(spies.setActiveTool).toHaveBeenCalledWith("select");
  });

  it("starts fresh after a commit", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawKeypointsTool.createHandler(ctx);

    placePoints(handler, setPointer, FACE_CLICKS);
    placePoints(handler, setPointer, FACE_CLICKS);

    expect(collection.byKind("keypoints")).toHaveLength(2);
  });

  it("reports which keys it consumed", () => {
    const { ctx } = makeHarness();
    const handler = drawKeypointsTool.createHandler(ctx);

    for (const key of ["Escape", "Backspace", "t", "i"]) {
      expect(handler.onKeyDown?.(new KeyboardEvent("keydown", { key }))).toBe(true);
    }
    expect(handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "a" }))).toBe(false);
  });
});
