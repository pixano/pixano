/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { drawMaskTool } from "../drawMaskTool.js";
import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";

// Konva needs a native canvas in node; the tool only builds a preview Image and
// a cursor Circle, and moves them around. Mock both with accessor objects.
vi.mock("konva", () => {
  class Image {
    private _image: unknown = null;
    destroyed = false;
    image(v?: unknown): unknown {
      if (v !== undefined) this._image = v;
      return this._image;
    }
    position(): void {}
    scale(): void {}
    destroy(): void {
      this.destroyed = true;
    }
  }
  class Circle {
    _pos: { x: number; y: number } | null = null;
    _radius = 0;
    _stroke = "";
    _fill = "";
    _visible = false;
    destroyed = false;
    constructor() {
      cursors.push(this);
    }
    position(p: { x: number; y: number }): void {
      this._pos = p;
    }
    radius(v: number): void {
      this._radius = v;
    }
    stroke(v: string): void {
      this._stroke = v;
    }
    fill(v: string): void {
      this._fill = v;
    }
    visible(v: boolean): void {
      this._visible = v;
    }
    destroy(): void {
      this.destroyed = true;
    }
  }
  return { default: { Image, Circle } };
});

/** Every cursor circle the tool has built, newest last. */
interface FakeCursor {
  _pos: { x: number; y: number } | null;
  _radius: number;
  _stroke: string;
  _fill: string;
  _visible: boolean;
  destroyed: boolean;
}
const cursors: FakeCursor[] = [];
const lastCursor = (): FakeCursor => cursors[cursors.length - 1];

// ─── Canvas harness ──────────────────────────────────────────────────────────
// The test DOM has no OffscreenCanvas. This fake models the brush at the grid
// level rather than rasterising: every `arc()` + `fill()` marks (or clears, in
// erase mode) the pixel at the arc centre. That is enough to drive the tool's
// real encode path — the exact stroke footprint is drawing, not data, and is
// left to manual verification.

const recorded = { compositeOps: [] as string[], lineWidths: [] as number[] };

class FakeImageData {
  readonly data: Uint8ClampedArray;
  constructor(
    readonly width: number,
    readonly height: number,
  ) {
    this.data = new Uint8ClampedArray(width * height * 4);
  }
}

class FakeOffscreenCanvas {
  private buffer: FakeImageData;
  constructor(
    readonly width: number,
    readonly height: number,
  ) {
    this.buffer = new FakeImageData(width, height);
  }
  getContext(): Record<string, unknown> {
    let pending: { x: number; y: number } | null = null;
    let composite = "source-over";
    // Arrow functions capture `this` lexically, so the fake reads and writes the
    // canvas buffer without aliasing it to a local.
    return {
      set globalCompositeOperation(v: string) {
        composite = v;
        recorded.compositeOps.push(v);
      },
      get globalCompositeOperation() {
        return composite;
      },
      set lineWidth(v: number) {
        recorded.lineWidths.push(v);
      },
      globalAlpha: 1,
      strokeStyle: "",
      fillStyle: "",
      lineCap: "",
      lineJoin: "",
      beginPath: () => {},
      moveTo: () => {},
      lineTo: () => {},
      stroke: () => {},
      arc: (x: number, y: number) => {
        pending = { x: Math.round(x), y: Math.round(y) };
      },
      fill: () => {
        if (!pending) return;
        const { x, y } = pending;
        if (x < 0 || y < 0 || x >= this.width || y >= this.height) return;
        this.buffer.data[(y * this.width + x) * 4 + 3] = composite === "destination-out" ? 0 : 255;
      },
      fillRect: () => {},
      drawImage: () => {},
      createImageData: (w: number, h: number) => new FakeImageData(w, h),
      putImageData: (d: FakeImageData) => {
        this.buffer = d;
      },
      getImageData: () => this.buffer,
    };
  }
}

beforeEach(() => {
  recorded.compositeOps = [];
  recorded.lineWidths = [];
  cursors.length = 0;
  vi.stubGlobal("OffscreenCanvas", FakeOffscreenCanvas);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ─── Scene harness ───────────────────────────────────────────────────────────

/** Image frame at the origin sized 100×100, matching a 100×100 media grid. */
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
  // Held apart from `ctx` so assertions reference plain functions rather than
  // methods read off an interface (which `@typescript-eslint/unbound-method`
  // rightly flags).
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
  NonNullable<ReturnType<typeof drawMaskTool.createHandler>["onPointerDown"]>
>[0];

const evt = () => ({ cancelBubble: false }) as PointerEvt;

/** Paint a short stroke, then finish it. */
function paintStroke(
  handler: ReturnType<typeof drawMaskTool.createHandler>,
  setPointer: (p: { x: number; y: number }) => void,
  points: { x: number; y: number }[],
): void {
  setPointer(points[0]);
  handler.onPointerDown?.(evt());
  for (const p of points.slice(1)) {
    setPointer(p);
    handler.onPointerMove?.(evt());
  }
  handler.onPointerUp?.(evt());
}

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("drawMaskTool metadata", () => {
  it("declares the mask kind so the toolbar can group it", () => {
    expect(drawMaskTool.kind).toBe("mask");
    expect(drawMaskTool.id).toBe("draw-mask");
  });
});

describe("drawMaskTool painting", () => {
  it("commits a mask draft on Enter after a stroke", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);
    handler.activate?.();

    paintStroke(handler, setPointer, [
      { x: 10, y: 10 },
      { x: 12, y: 12 },
    ]);
    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Enter" }));

    const masks = collection.byKind("mask");
    expect(masks).toHaveLength(1);
    expect(masks[0].persisted).toBe(false);
    expect(masks[0].entityId).toBe("");
    expect(masks[0].viewId).toBe("view-1");
    expect(masks[0].geometry.size).toEqual([100, 100]);
    expect(masks[0].geometry.counts.length).toBeGreaterThan(0);
  });

  it("asks for an entity and hands control back to select", () => {
    const { ctx, spies, setPointer } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);

    paintStroke(handler, setPointer, [{ x: 20, y: 20 }]);
    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Enter" }));

    expect(spies.beginPendingAnnotation).toHaveBeenCalledTimes(1);
    expect(spies.setActiveTool).toHaveBeenCalledWith("select");
  });

  it("commits nothing when Enter is pressed without painting", () => {
    const { ctx, collection, spies } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);

    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Enter" }));

    expect(collection.byKind("mask")).toHaveLength(0);
    expect(spies.beginPendingAnnotation).not.toHaveBeenCalled();
    expect(spies.setActiveTool).toHaveBeenCalledWith("select");
  });

  it("discards the stroke on Escape", () => {
    const { ctx, collection, spies, setPointer } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);

    paintStroke(handler, setPointer, [{ x: 30, y: 30 }]);
    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Escape" }));

    expect(collection.byKind("mask")).toHaveLength(0);
    expect(spies.setActiveTool).toHaveBeenCalledWith("select");
  });

  it("starts a fresh raster after a commit", () => {
    // The second stroke must not inherit the first one's pixels.
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);

    paintStroke(handler, setPointer, [{ x: 10, y: 10 }]);
    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Enter" }));
    paintStroke(handler, setPointer, [{ x: 80, y: 80 }]);
    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Enter" }));

    const masks = collection.byKind("mask");
    expect(masks).toHaveLength(2);
    expect(masks[0].geometry.counts).not.toBe(masks[1].geometry.counts);
  });

  it("paints nothing when the image frame is unavailable", () => {
    const { ctx, collection, setPointer } = makeHarness({ image: null });
    const handler = drawMaskTool.createHandler(ctx);

    paintStroke(handler, setPointer, [{ x: 10, y: 10 }]);
    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Enter" }));

    expect(collection.byKind("mask")).toHaveLength(0);
  });
});

describe("drawMaskTool brush settings", () => {
  it("toggles between draw and erase on X", () => {
    const { ctx, setPointer } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);

    paintStroke(handler, setPointer, [{ x: 10, y: 10 }]);
    expect(recorded.compositeOps).toContain("source-over");

    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "x" }));
    paintStroke(handler, setPointer, [{ x: 10, y: 10 }]);
    expect(recorded.compositeOps).toContain("destination-out");
  });

  it("erasing the whole stroke commits nothing", () => {
    const { ctx, collection, setPointer } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);

    paintStroke(handler, setPointer, [{ x: 40, y: 40 }]);
    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "x" }));
    paintStroke(handler, setPointer, [{ x: 40, y: 40 }]);
    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Enter" }));

    expect(collection.byKind("mask")).toHaveLength(0);
  });

  it("grows and shrinks the brush with ] and [", () => {
    const { ctx, setPointer } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);

    paintStroke(handler, setPointer, [{ x: 10, y: 10 }]);
    const initial = recorded.lineWidths.at(-1)!;

    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "]" }));
    paintStroke(handler, setPointer, [{ x: 10, y: 10 }]);
    expect(recorded.lineWidths.at(-1)!).toBeGreaterThan(initial);

    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "[" }));
    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "[" }));
    paintStroke(handler, setPointer, [{ x: 10, y: 10 }]);
    expect(recorded.lineWidths.at(-1)!).toBeLessThan(initial);
  });

  it("reports which keys it consumed", () => {
    const { ctx } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);

    for (const key of ["Escape", "Enter", "x", "[", "]"]) {
      expect(handler.onKeyDown?.(new KeyboardEvent("keydown", { key }))).toBe(true);
    }
    expect(handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "a" }))).toBe(false);
  });
});

describe("drawMaskTool brush cursor", () => {
  it("hides the OS cursor, since the outline replaces it", () => {
    expect(drawMaskTool.cursor).toBe("none");
  });

  it("follows the pointer without a stroke in progress", () => {
    // Seeing the brush size *before* committing to a stroke is the whole point.
    const { ctx, setPointer } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);
    handler.activate?.();

    setPointer({ x: 42, y: 24 });
    handler.onPointerMove?.(evt());

    expect(lastCursor()._pos).toEqual({ x: 42, y: 24 });
    expect(lastCursor()._visible).toBe(true);
  });

  it("matches the brush radius in display pixels", () => {
    const { ctx, setPointer } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);

    setPointer({ x: 10, y: 10 });
    handler.onPointerMove?.(evt());
    const initial = lastCursor()._radius;

    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "]" }));
    expect(lastCursor()._radius).toBeGreaterThan(initial);

    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "[" }));
    expect(lastCursor()._radius).toBe(initial);
  });

  it("turns red in erase mode and back to green on toggle", () => {
    const { ctx, setPointer } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);

    setPointer({ x: 10, y: 10 });
    handler.onPointerMove?.(evt());
    expect(lastCursor()._stroke).toContain("0, 200, 0");

    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "x" }));
    expect(lastCursor()._stroke).toContain("200, 0, 0");

    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "x" }));
    expect(lastCursor()._stroke).toContain("0, 200, 0");
  });

  it("hides when the pointer leaves the stage", () => {
    const { ctx, setPointer } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);

    setPointer({ x: 10, y: 10 });
    handler.onPointerMove?.(evt());
    setPointer(null);
    handler.onPointerMove?.(evt());

    expect(lastCursor()._visible).toBe(false);
  });

  it("survives a commit but is destroyed when the tool is deactivated", () => {
    // It tracks the pointer between strokes, so a commit must not tear it down.
    const { ctx, setPointer } = makeHarness();
    const handler = drawMaskTool.createHandler(ctx);

    paintStroke(handler, setPointer, [{ x: 10, y: 10 }]);
    handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Enter" }));
    expect(lastCursor().destroyed).toBe(false);

    handler.deactivate?.();
    expect(lastCursor().destroyed).toBe(true);
  });
});
