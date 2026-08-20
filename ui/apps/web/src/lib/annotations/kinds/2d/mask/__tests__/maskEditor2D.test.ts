/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createMaskEditor2D } from "../maskEditor2D.js";
import { MASK_ID_ATTR, MASK_NODE_NAME, type MaskGeometry } from "../maskTypes.js";
import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";

// The test DOM has no OffscreenCanvas, so the raster round-trip is stubbed:
// what matters here is the pixel→grid conversion handed to `translateMask`.
const translateMask = vi.hoisted(() => vi.fn());
vi.mock("../maskRaster.js", () => ({ translateMask }));

const GEOMETRY: MaskGeometry = { size: [200, 400], counts: "abc" };

function fakeNode(opts: { id?: string; x?: number; y?: number; name?: string }) {
  return {
    name: () => opts.name ?? MASK_NODE_NAME,
    getAttr: (k: string) => (k === MASK_ID_ATTR ? (opts.id ?? "a1") : undefined),
    x: () => opts.x ?? 0,
    y: () => opts.y ?? 0,
  };
}

function makeHarness() {
  const collection = new AnnotationCollection();
  const handlers: Record<string, (e: { target: unknown }) => void> = {};
  const upsertUpdate = vi.fn();
  const off = vi.fn();
  const requestRedraw = vi.fn();
  const ctx = {
    widgetId: "w1",
    buildContext: { datasetId: "ds", recordId: "rec", viewId: "view-1" },
    collection,
    mutations: {
      pending: [],
      queue: vi.fn(),
      upsertUpdate,
      patchPendingCreate: vi.fn(),
      dropForLocalAnnotation: vi.fn(),
    },
    annotationLayer: {
      on: (evt: string, fn: (e: { target: unknown }) => void) => (handlers[evt] = fn),
      off,
    } as unknown as Konva.Layer,
    // Frame at the origin, 100×50 on screen for a 400×200 mask grid → ×4 / ×4.
    getKonvaImage: () =>
      ({ x: () => 0, y: () => 0, width: () => 100, height: () => 50 }) as unknown as Konva.Image,
    requestRedraw,
  } as unknown as Scene2DContext;
  return { ctx, collection, handlers, upsertUpdate, off, requestRedraw };
}

describe("maskEditor2D", () => {
  let harness: ReturnType<typeof makeHarness>;
  const drag = (target: unknown) => harness.handlers["dragend.mask-edit"]({ target });

  beforeEach(() => {
    translateMask.mockReset();
    harness = makeHarness();
    createMaskEditor2D(harness.ctx);
    harness.collection.add({
      id: "a1",
      entityId: "e1",
      kind: "mask",
      viewId: "view-1",
      geometry: GEOMETRY,
      persisted: true,
    });
  });

  it("converts the stage-pixel drag into the mask's own grid", () => {
    translateMask.mockReturnValue({ size: [200, 400], counts: "moved" });

    // 10 stage px across a 100px-wide frame standing in for a 400px grid → 40.
    drag(fakeNode({ x: 10, y: 5 }));

    expect(translateMask).toHaveBeenCalledWith(GEOMETRY, 40, 20);
    expect(harness.collection.find("a1")?.geometry).toEqual({ size: [200, 400], counts: "moved" });
    expect(harness.upsertUpdate).toHaveBeenCalledTimes(1);
  });

  it("commits nothing when the re-encode fails, and asks for a resync", () => {
    translateMask.mockReturnValue(null);

    drag(fakeNode({ x: 10, y: 5 }));

    // Unchanged, not merely equal-looking: compared by value because the
    // collection stores geometry behind a reactive proxy.
    expect(harness.collection.find("a1")?.geometry).toEqual(GEOMETRY);
    expect(harness.upsertUpdate).not.toHaveBeenCalled();
    // Without a redraw the node would stay where it was dropped.
    expect(harness.requestRedraw).toHaveBeenCalled();
  });

  it("ignores nodes belonging to another kind", () => {
    drag(fakeNode({ name: "pixano-bbox" }));

    expect(translateMask).not.toHaveBeenCalled();
  });

  it("ignores a drag on an annotation that is gone", () => {
    drag(fakeNode({ id: "vanished" }));

    expect(translateMask).not.toHaveBeenCalled();
  });

  it("stops listening once destroyed", () => {
    createMaskEditor2D(harness.ctx).destroy();

    expect(harness.off).toHaveBeenCalledWith("dragend.mask-edit");
  });
});
