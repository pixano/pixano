/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Konva needs a native canvas in node; the tool only constructs a Rect and
// reads/writes its geometry. Mock it with a plain accessor object.
vi.mock("konva", () => {
  class Rect {
    private _x: number;
    private _y: number;
    private _w: number;
    private _h: number;
    destroyed = false;
    constructor(cfg: { x: number; y: number; width: number; height: number }) {
      this._x = cfg.x;
      this._y = cfg.y;
      this._w = cfg.width;
      this._h = cfg.height;
    }
    position(p: { x: number; y: number }): void {
      this._x = p.x;
      this._y = p.y;
    }
    x(): number {
      return this._x;
    }
    y(): number {
      return this._y;
    }
    width(v?: number): number {
      if (v !== undefined) this._w = v;
      return this._w;
    }
    height(v?: number): number {
      if (v !== undefined) this._h = v;
      return this._h;
    }
    destroy(): void {
      this.destroyed = true;
    }
  }
  return { default: { Rect } };
});

import { AnnotationCollection, type BBoxGeometry } from "$lib/annotations/annotationCollection.svelte.js";
import type { CoordsNorm } from "$lib/annotations/types.js";

import { drawBBoxTool } from "../drawBBoxTool.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";

// ─── Harness ─────────────────────────────────────────────────────────────────

// Image frame at the origin sized 100×100 so pixel == percent in assertions.
function fakeImage(x = 0, y = 0, w = 100, h = 100): Konva.Image {
  return { x: () => x, y: () => y, width: () => w, height: () => h } as unknown as Konva.Image;
}

function makeHarness(opts: { image?: Konva.Image | null } = {}) {
  const collection = new AnnotationCollection();
  let pointer: { x: number; y: number } | null = null;
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
    stage: { getPointerPosition: () => pointer } as unknown as Konva.Stage,
    annotationLayer: { add: vi.fn(), batchDraw: vi.fn() } as unknown as Konva.Layer,
    camera: { imageWidth: 100, imageHeight: 100, calibration: null },
    getKonvaImage: () => ("image" in opts ? (opts.image ?? null) : fakeImage()),
    setActiveTool: vi.fn(),
    requestRedraw: vi.fn(),
    beginPendingAnnotation: vi.fn(),
    findEntity: vi.fn(),
    isEntityVisible: () => true,
  };
  return { ctx, collection, setPointer: (p: { x: number; y: number } | null) => (pointer = p) };
}

type PointerEvt = Parameters<NonNullable<ReturnType<typeof drawBBoxTool.createHandler>["onPointerDown"]>>[0];
const pointerEvent = () => ({ cancelBubble: false }) as PointerEvt;

/** Drive a full down→move→up gesture between two stage points. */
function drag(
  handler: ReturnType<typeof drawBBoxTool.createHandler>,
  setPointer: (p: { x: number; y: number }) => void,
  from: { x: number; y: number },
  to: { x: number; y: number },
) {
  setPointer(from);
  handler.onPointerDown!(pointerEvent());
  setPointer(to);
  handler.onPointerMove!(pointerEvent());
  handler.onPointerUp!(pointerEvent());
}

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("drawBBoxTool", () => {
  it("declares its toolbar metadata for the bbox kind", () => {
    expect(drawBBoxTool).toMatchObject({ id: "draw-bbox", kind: "bbox", cursor: "crosshair" });
  });

  let harness: ReturnType<typeof makeHarness>;
  let handler: ReturnType<typeof drawBBoxTool.createHandler>;
  beforeEach(() => {
    harness = makeHarness();
    handler = drawBBoxTool.createHandler(harness.ctx);
  });

  it("adds a draft (no entity yet), selects it, and opens the entity-assignment flow", () => {
    drag(handler, harness.setPointer, { x: 10, y: 20 }, { x: 60, y: 80 });

    expect(harness.collection.count).toBe(1);
    const bbox = harness.collection.items[0];
    expect(bbox).toMatchObject({ kind: "bbox", viewId: "view-1", persisted: false, entityId: "" });
    // (10,20)→(60,80) on a 100×100 frame at origin → x,y,w,h normalized.
    expect(bbox.geometry as CoordsNorm).toEqual([0.1, 0.2, 0.5, 0.6]);

    // The draft is shown immediately; nothing is queued until the user confirms.
    expect(harness.ctx.mutations.queue).not.toHaveBeenCalled();
    expect(harness.collection.selectedId).toBe(bbox.id);
    expect(harness.ctx.setActiveTool).toHaveBeenCalledWith("select");
    expect(harness.ctx.beginPendingAnnotation).toHaveBeenCalledTimes(1);
  });

  it("on confirm with a new entity, sets the entityId and queues the entity + bbox creates", () => {
    drag(handler, harness.setPointer, { x: 10, y: 20 }, { x: 60, y: 80 });
    const pending = vi.mocked(harness.ctx.beginPendingAnnotation).mock.calls[0][0];

    pending.onConfirm({ mode: "new", entityFields: { category: "car" } });

    const bbox = harness.collection.items[0];
    expect(bbox.entityId).not.toBe("");
    expect(bbox.entity).toMatchObject({ category: "car" });
    expect(harness.ctx.mutations.queue).toHaveBeenCalledTimes(2); // entity + bbox
  });

  it("on confirm linking an existing entity, reuses its id and queues only the bbox create", () => {
    vi.mocked(harness.ctx.findEntity).mockReturnValue({ id: "ent-9", category: "bus" });
    drag(handler, harness.setPointer, { x: 10, y: 20 }, { x: 60, y: 80 });
    const pending = vi.mocked(harness.ctx.beginPendingAnnotation).mock.calls[0][0];

    pending.onConfirm({ mode: "existing", entityId: "ent-9" });

    const bbox = harness.collection.items[0];
    expect(bbox.entityId).toBe("ent-9");
    expect(harness.ctx.mutations.queue).toHaveBeenCalledTimes(1); // bbox only; entity already exists
  });

  it("on cancel, discards the draft", () => {
    drag(handler, harness.setPointer, { x: 10, y: 20 }, { x: 60, y: 80 });
    const pending = vi.mocked(harness.ctx.beginPendingAnnotation).mock.calls[0][0];

    pending.onCancel();

    expect(harness.collection.count).toBe(0);
    expect(harness.ctx.mutations.queue).not.toHaveBeenCalled();
  });

  it("clamps a box drawn partly outside the image to the frame", () => {
    drag(handler, harness.setPointer, { x: -20, y: -10 }, { x: 40, y: 50 });

    const geometry = harness.collection.items[0].geometry as CoordsNorm;
    // left/top clamp to 0; right/bottom keep 40/50 → w=0.4, h=0.5.
    expect(geometry).toEqual([0, 0, 0.4, 0.5]);
  });

  it("rejects a sub-threshold (click-sized) box without committing", () => {
    drag(handler, harness.setPointer, { x: 30, y: 30 }, { x: 31, y: 31 });

    expect(harness.collection.count).toBe(0);
    expect(harness.ctx.mutations.queue).not.toHaveBeenCalled();
    expect(harness.ctx.setActiveTool).toHaveBeenCalledWith("select");
  });

  it("commits nothing and returns to select when the image isn't loaded", () => {
    const h2 = makeHarness({ image: null });
    const handler2 = drawBBoxTool.createHandler(h2.ctx);
    drag(handler2, h2.setPointer, { x: 10, y: 10 }, { x: 60, y: 60 });

    expect(h2.collection.count).toBe(0);
    expect(h2.ctx.mutations.queue).not.toHaveBeenCalled();
    expect(h2.ctx.setActiveTool).toHaveBeenCalledWith("select");
  });

  it("Escape cancels the in-progress draft without committing", () => {
    harness.setPointer({ x: 10, y: 20 });
    handler.onPointerDown!(pointerEvent());

    expect(handler.onKeyDown!(new KeyboardEvent("keydown", { key: "Escape" }))).toBe(true);
    // A subsequent pointer-up has no draft to commit.
    handler.onPointerUp!(pointerEvent());

    expect(harness.collection.count).toBe(0);
    expect(harness.ctx.mutations.queue).not.toHaveBeenCalled();
    expect(harness.ctx.setActiveTool).toHaveBeenCalledWith("select");
  });

  it("ignores a pointer-move with no active draft", () => {
    harness.setPointer({ x: 5, y: 5 });
    expect(() => handler.onPointerMove!(pointerEvent())).not.toThrow();
    expect(harness.ctx.annotationLayer.batchDraw).not.toHaveBeenCalled();
  });

  it("typed geometry: a committed bbox carries a 4-tuple", () => {
    drag(handler, harness.setPointer, { x: 10, y: 10 }, { x: 50, y: 50 });
    const g = harness.collection.byKind("bbox")[0].geometry satisfies BBoxGeometry;
    expect(g).toHaveLength(4);
  });
});
