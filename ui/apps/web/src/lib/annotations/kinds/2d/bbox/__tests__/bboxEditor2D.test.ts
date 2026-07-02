/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { beforeEach, describe, expect, it, vi } from "vitest";

// The editor only constructs a Konva.Transformer; the layer + nodes are fakes
// supplied by the harness, so we mock just the Transformer.
vi.mock("konva", () => {
  class Transformer {
    nodes = vi.fn();
    moveToTop = vi.fn();
    destroy = vi.fn();
    getLayer = () => ({ batchDraw: vi.fn() });
    constructor(_cfg: unknown) {}
  }
  return { default: { Transformer } };
});

import { AnnotationCollection, type BBoxGeometry } from "$lib/annotations/annotationCollection.svelte.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";

import { createBBoxEditor2D } from "../bboxEditor2D.js";

function fakeImage(w = 100, h = 100): Konva.Image {
  return { x: () => 0, y: () => 0, width: () => w, height: () => h } as unknown as Konva.Image;
}

/** A bbox rect node as the renderer would stamp it. */
function fakeRect(opts: {
  id: string;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  scaleX?: number;
  scaleY?: number;
  name?: string;
}) {
  let w = opts.w ?? 30;
  let h = opts.h ?? 40;
  let sx = opts.scaleX ?? 1;
  let sy = opts.scaleY ?? 1;
  return {
    name: () => opts.name ?? "bbox",
    getAttr: (k: string) => (k === "bboxId" ? opts.id : undefined),
    x: () => opts.x ?? 10,
    y: () => opts.y ?? 20,
    width: (v?: number) => (v !== undefined ? (w = v) : w),
    height: (v?: number) => (v !== undefined ? (h = v) : h),
    scaleX: (v?: number) => (v !== undefined ? (sx = v) : sx),
    scaleY: (v?: number) => (v !== undefined ? (sy = v) : sy),
  };
}

function makeHarness() {
  const collection = new AnnotationCollection();
  const handlers: Record<string, (e: { target: unknown }) => void> = {};
  const ctx = {
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
    stage: {} as unknown as Konva.Stage,
    annotationLayer: {
      add: vi.fn(),
      on: (evt: string, fn: (e: { target: unknown }) => void) => (handlers[evt] = fn),
      off: vi.fn(),
      find: vi.fn(() => []),
      batchDraw: vi.fn(),
    } as unknown as Konva.Layer,
    getKonvaImage: () => fakeImage(),
    setActiveTool: vi.fn(),
    requestRedraw: vi.fn(),
  } as unknown as Scene2DContext;
  return { ctx, collection, handlers };
}

describe("bboxEditor2D", () => {
  let harness: ReturnType<typeof makeHarness>;
  beforeEach(() => {
    harness = makeHarness();
    createBBoxEditor2D(harness.ctx);
  });

  it("commits a dragged box: writes geometry and queues an update (persisted)", () => {
    harness.collection.add({
      id: "a1",
      entityId: "e1",
      kind: "bbox",
      viewId: "view-1",
      geometry: [0, 0, 0.1, 0.1] as BBoxGeometry,
      persisted: true,
    });

    harness.handlers["dragend.bbox-edit"]({ target: fakeRect({ id: "a1", x: 10, y: 20, w: 30, h: 40 }) });

    // pixel (10,20,30,40) over a 100×100 frame → normalized [0.1,0.2,0.3,0.4].
    expect(harness.collection.find("a1")?.geometry).toEqual([0.1, 0.2, 0.3, 0.4]);
    expect(harness.ctx.mutations.upsertUpdate).toHaveBeenCalledTimes(1);
  });

  it("bakes the transform scale into width/height before committing", () => {
    harness.collection.add({
      id: "a1",
      entityId: "e1",
      kind: "bbox",
      viewId: "view-1",
      geometry: [0, 0, 0.1, 0.1] as BBoxGeometry,
      persisted: false,
    });

    // 30×40 scaled ×2 → 60×80 → normalized width/height 0.6/0.8.
    harness.handlers["transformend.bbox-edit"]({
      target: fakeRect({ id: "a1", x: 10, y: 20, w: 30, h: 40, scaleX: 2, scaleY: 2 }),
    });

    expect(harness.collection.find("a1")?.geometry).toEqual([0.1, 0.2, 0.6, 0.8]);
    // Draft → patches the pending create, not an update.
    expect(harness.ctx.mutations.patchPendingCreate).toHaveBeenCalledTimes(1);
    expect(harness.ctx.mutations.upsertUpdate).not.toHaveBeenCalled();
  });

  it("ignores nodes that are not bbox rects", () => {
    harness.handlers["dragend.bbox-edit"]({ target: fakeRect({ id: "x", name: "other" }) });
    expect(harness.ctx.mutations.upsertUpdate).not.toHaveBeenCalled();
    expect(harness.ctx.mutations.patchPendingCreate).not.toHaveBeenCalled();
  });
});
