/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { describe, expect, it, vi } from "vitest";

import { SmartSegmentHandler, smartSegmentTool } from "../smartSegmentTool.js";
import type { SegmentationBackend } from "../smartSegmentTool.js";
import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { LocalMask } from "$lib/annotations/annotationCollection.svelte.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import type { PendingAnnotation } from "$lib/annotations/types.js";

// Konva needs a native canvas in node; the tool only builds prompt markers.
vi.mock("konva", () => {
  class Node {
    add(): void {}
    destroy(): void {}
  }
  return { default: { Group: Node, Circle: Node, Text: Node } };
});

// ─── Harness ─────────────────────────────────────────────────────────────────

/** Frame at the origin sized 100×100 over a 200×400 image, so the two grids differ. */
function fakeImage(): Konva.Image {
  return {
    x: () => 0,
    y: () => 0,
    width: () => 100,
    height: () => 100,
  } as unknown as Konva.Image;
}

const SAMPLE_MASK = { size: [400, 200] as [number, number], counts: "a2b1" };

function makeHarness(backend: Partial<SegmentationBackend> = {}) {
  const collection = new AnnotationCollection();
  let pointer: { x: number; y: number } | null = null;
  let pending: PendingAnnotation | null = null;
  const spies = { setActiveTool: vi.fn(), requestRedraw: vi.fn() };
  const calls: { segment: Parameters<SegmentationBackend["segment"]>[0][] } = { segment: [] };

  // One recording wrapper around whichever stub the test supplied, so every
  // request is logged exactly once whether or not `segment` was overridden.
  const listModels = backend.listModels ?? (() => Promise.resolve([{ name: "sam2" }]));
  const segment = backend.segment ?? (() => Promise.resolve([SAMPLE_MASK]));
  const recording: SegmentationBackend = {
    listModels: (task) => listModels(task),
    segment: (request) => {
      calls.segment.push(request);
      return segment(request);
    },
  };

  const ctx: Scene2DContext = {
    widgetId: "w1",
    buildContext: { datasetId: "ds-1", recordId: "rec", viewId: "view-1" },
    collection,
    mutations: {
      pending: [],
      queue: vi.fn(),
      upsertUpdate: vi.fn(),
      patchPendingCreate: vi.fn(),
      dropForLocalAnnotation: vi.fn(),
    },
    liveDraft: { get: () => null },
    stage: { getPointerPosition: () => pointer } as unknown as Konva.Stage,
    annotationLayer: { add: vi.fn(), batchDraw: vi.fn() } as unknown as Konva.Layer,
    camera: { imageWidth: 200, imageHeight: 400, calibration: null },
    getKonvaImage: () => fakeImage(),
    ...spies,
    beginPendingAnnotation: (p: PendingAnnotation) => (pending = p),
    findEntity: vi.fn(),
    isEntityVisible: () => true,
  };

  return {
    handler: new SmartSegmentHandler(ctx, recording),
    collection,
    spies,
    calls,
    pendingLabel: () => pending?.label,
    setPointer: (p: { x: number; y: number } | null) => (pointer = p),
  };
}

type PointerEvt = Parameters<NonNullable<ToolHandlerLike["onPointerDown"]>>[0];
type ToolHandlerLike = ReturnType<typeof smartSegmentTool.createHandler>;

const evt = () => ({ cancelBubble: false }) as PointerEvt;
const key = (k: string) => new KeyboardEvent("keydown", { key: k });

function clickAt(
  h: { handler: SmartSegmentHandler; setPointer: (p: { x: number; y: number }) => void },
  points: { x: number; y: number }[],
): void {
  for (const p of points) {
    h.setPointer(p);
    h.handler.onPointerDown?.(evt());
  }
}

/** Let the tool's async segmentation settle. */
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

const firstMask = (collection: AnnotationCollection): LocalMask =>
  collection.byKind("mask")[0] as LocalMask;

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("smartSegmentTool metadata", () => {
  it("produces masks rather than a kind of its own", () => {
    // The model and the brush describe a region differently but store the same
    // thing, so they share the kind and its payload builder.
    expect(smartSegmentTool.kind).toBe("mask");
    expect(smartSegmentTool.id).toBe("smart-segment");
  });
});

describe("smart segmentation prompts", () => {
  it("sends prompts in the image's pixel grid, not display pixels", async () => {
    // The frame is 100×100 on screen over a 200×400 image, so a click at the
    // middle of the frame is (100, 200) in the grid the model runs on.
    const h = makeHarness();
    clickAt(h, [{ x: 50, y: 50 }]);
    h.handler.onKeyDown?.(key("Enter"));
    await flush();

    expect(h.calls.segment[0].prompt.points).toEqual([[100, 200]]);
  });

  it("labels points 1 for include and 0 for exclude", async () => {
    const h = makeHarness();
    clickAt(h, [{ x: 10, y: 10 }]);
    h.handler.onKeyDown?.(key("x"));
    clickAt(h, [{ x: 20, y: 20 }]);
    h.handler.onKeyDown?.(key("Enter"));
    await flush();

    expect(h.calls.segment[0].prompt.labels).toEqual([1, 0]);
  });

  it("removes the last prompt on Backspace", async () => {
    const h = makeHarness();
    clickAt(h, [
      { x: 10, y: 10 },
      { x: 20, y: 20 },
    ]);
    h.handler.onKeyDown?.(key("Backspace"));
    h.handler.onKeyDown?.(key("Enter"));
    await flush();

    expect(h.calls.segment[0].prompt.points).toHaveLength(1);
  });

  it("forwards the dataset and view the model must read", async () => {
    const h = makeHarness();
    clickAt(h, [{ x: 10, y: 10 }]);
    h.handler.onKeyDown?.(key("Enter"));
    await flush();

    expect(h.calls.segment[0]).toMatchObject({
      datasetId: "ds-1",
      viewId: "view-1",
      model: "sam2",
    });
  });
});

describe("smart segmentation results", () => {
  it("commits the returned mask as an ordinary draft", async () => {
    const h = makeHarness();
    clickAt(h, [{ x: 10, y: 10 }]);
    h.handler.onKeyDown?.(key("Enter"));
    await flush();

    const mask = firstMask(h.collection);
    expect(mask.kind).toBe("mask");
    expect(mask.persisted).toBe(false);
    expect(mask.geometry).toEqual({ size: [400, 200], counts: "a2b1" });
  });

  it("asks for an entity and hands control back to select", async () => {
    const h = makeHarness();
    clickAt(h, [{ x: 10, y: 10 }]);
    h.handler.onKeyDown?.(key("Enter"));
    await flush();

    expect(h.pendingLabel()).toBe("mask");
    expect(h.spies.setActiveTool).toHaveBeenCalledWith("select");
  });

  it("keeps the prompts and commits nothing when the model returns none", async () => {
    const h = makeHarness({ segment: () => Promise.resolve([]) });
    clickAt(h, [{ x: 10, y: 10 }]);
    h.handler.onKeyDown?.(key("Enter"));
    await flush();

    expect(h.collection.byKind("mask")).toHaveLength(0);
    // Still usable: a second Enter re-runs with the same prompts.
    h.handler.onKeyDown?.(key("Enter"));
    await flush();
    expect(h.calls.segment).toHaveLength(2);
  });

  it("rejects a mask with a degenerate grid", async () => {
    const h = makeHarness({ segment: () => Promise.resolve([{ size: [0, 0], counts: "" }]) });
    clickAt(h, [{ x: 10, y: 10 }]);
    h.handler.onKeyDown?.(key("Enter"));
    await flush();

    expect(h.collection.byKind("mask")).toHaveLength(0);
  });
});

describe("smart segmentation failure paths", () => {
  it("runs nothing without a connected model", async () => {
    // The common case in development, so it must fail quietly rather than throw.
    const h = makeHarness({ listModels: () => Promise.resolve([]) });
    clickAt(h, [{ x: 10, y: 10 }]);
    h.handler.onKeyDown?.(key("Enter"));
    await flush();

    expect(h.calls.segment).toHaveLength(0);
    expect(h.collection.byKind("mask")).toHaveLength(0);
  });

  it("survives a failing inference call", async () => {
    const h = makeHarness({ segment: () => Promise.reject(new Error("boom")) });
    clickAt(h, [{ x: 10, y: 10 }]);

    expect(() => h.handler.onKeyDown?.(key("Enter"))).not.toThrow();
    await flush();
    expect(h.collection.byKind("mask")).toHaveLength(0);
  });

  it("refuses a prompt with no include point", async () => {
    // Only-negative prompts describe nothing to segment.
    const h = makeHarness();
    h.handler.onKeyDown?.(key("x"));
    clickAt(h, [{ x: 10, y: 10 }]);
    h.handler.onKeyDown?.(key("Enter"));
    await flush();

    expect(h.calls.segment).toHaveLength(0);
  });

  it("runs nothing with no prompt at all", async () => {
    const h = makeHarness();
    h.handler.onKeyDown?.(key("Enter"));
    await flush();

    expect(h.calls.segment).toHaveLength(0);
  });

  it("clears its prompts on Escape", async () => {
    const h = makeHarness();
    clickAt(h, [{ x: 10, y: 10 }]);
    h.handler.onKeyDown?.(key("Escape"));
    h.handler.onKeyDown?.(key("Enter"));
    await flush();

    expect(h.calls.segment).toHaveLength(0);
    expect(h.spies.setActiveTool).toHaveBeenCalledWith("select");
  });

  it("reports which keys it consumed", () => {
    const h = makeHarness();
    for (const k of ["Escape", "Enter", "x", "Backspace"]) {
      expect(h.handler.onKeyDown?.(key(k))).toBe(true);
    }
    expect(h.handler.onKeyDown?.(key("a"))).toBe(false);
  });
});
