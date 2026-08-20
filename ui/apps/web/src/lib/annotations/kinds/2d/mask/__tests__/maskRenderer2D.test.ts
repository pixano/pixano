/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { maskRenderer2DFactory } from "../maskRenderer2D.js";
import type { MaskGeometry } from "../maskTypes.js";
import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { Scene2DReadContext } from "$lib/annotations/scene/sceneContext.js";

// The raster round-trip is stubbed: what matters here is *how often* the
// renderer decides to re-tint, which is the cache key's whole job.
const decodeMask = vi.hoisted(() => vi.fn());
const tintMask = vi.hoisted(() => vi.fn());
vi.mock("../maskRaster.js", () => ({ decodeMask, tintMask }));

vi.mock("konva", () => {
  class Image {
    attrs: Record<string, unknown> = {};
    constructor(public cfg: Record<string, unknown> = {}) {}
    setAttr(key: string, value: unknown) {
      this.attrs[key] = value;
    }
    on() {}
    image() {
      return { width: 10, height: 10 };
    }
    position() {}
    scale() {}
    cache() {}
    drawHitFromCache() {}
    destroy() {}
  }
  return { default: { Image } };
});

const GEOMETRY: MaskGeometry = { size: [10, 10], counts: "abc" };

function makeHarness() {
  const collection = new AnnotationCollection();
  const ctx = {
    collection,
    annotationLayer: { add: vi.fn(), batchDraw: vi.fn() } as unknown as Konva.Layer,
    getKonvaImage: () =>
      ({ x: () => 0, y: () => 0, width: () => 100, height: () => 100 }) as unknown as Konva.Image,
    isEntityVisible: () => true,
  } as unknown as Scene2DReadContext;
  collection.add({
    id: "m1",
    entityId: "e1",
    kind: "mask",
    viewId: "v1",
    geometry: GEOMETRY,
    persisted: true,
  });
  return { ctx, collection };
}

describe("maskRenderer2D", () => {
  let harness: ReturnType<typeof makeHarness>;

  beforeEach(() => {
    decodeMask.mockReset().mockReturnValue({ width: 10, height: 10 });
    tintMask.mockReset().mockReturnValue({ width: 10, height: 10 });
    harness = makeHarness();
  });

  it("re-tints when the selection changes, since opacity is baked into the raster", () => {
    const renderer = maskRenderer2DFactory.create(harness.ctx);
    renderer.sync();
    const afterFirst = tintMask.mock.calls.length;

    harness.collection.select("m1");
    renderer.sync();

    // Konva's node opacity can only scale a baked alpha *down*, so a mask that
    // reads as more solid when selected has to go back through the tint.
    expect(tintMask.mock.calls.length).toBeGreaterThan(afterFirst);
  });

  it("raises the opacity rather than lowering it when selected", () => {
    const renderer = maskRenderer2DFactory.create(harness.ctx);
    renderer.sync();
    const idleOpacity = tintMask.mock.calls[0][2] as number;

    harness.collection.select("m1");
    renderer.sync();
    const selectedOpacity = tintMask.mock.calls.at(-1)?.[2] as number;

    expect(selectedOpacity).toBeGreaterThan(idleOpacity);
    // Still translucent: an opaque mask hides the pixels being checked.
    expect(selectedOpacity).toBeLessThan(1);
  });

  it("does not re-tint when nothing about the mask changed", () => {
    const renderer = maskRenderer2DFactory.create(harness.ctx);
    renderer.sync();
    const afterFirst = tintMask.mock.calls.length;

    // Decoding an RLE is the expensive part of a sync, and sync() runs on every
    // collection change — a neighbouring annotation moving must not pay for it.
    renderer.sync();

    expect(tintMask.mock.calls.length).toBe(afterFirst);
  });

  it("re-tints when the geometry changes", () => {
    const renderer = maskRenderer2DFactory.create(harness.ctx);
    renderer.sync();
    const afterFirst = tintMask.mock.calls.length;

    harness.collection.setGeometry("m1", { size: [10, 10], counts: "different" });
    renderer.sync();

    expect(tintMask.mock.calls.length).toBeGreaterThan(afterFirst);
  });
});
