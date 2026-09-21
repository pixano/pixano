/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { MultiPathGeometry } from "$lib/annotations/kinds/2d/multi-path/multiPathTypes.js";
import {
  createFlatCoordsEditor2D,
  type FlatCoordsEditorSpec,
} from "$lib/annotations/scene/flatCoordsEditor2D.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";

const ID_ATTR = "theId";
const INDEX_ATTR = "theIndex";
const VERTEX_NAME = "vertex";

/**
 * Exercised through the real `multi_path` kind rather than a stand-in geometry,
 * so the edit goes through that kind's actual payload builder — the per-kind
 * extras a drag must preserve (`numPoints`, `isClosed`) are real fields.
 */
const spec: FlatCoordsEditorSpec<MultiPathGeometry> = {
  kind: "multi_path",
  idAttr: ID_ATTR,
  vertexName: VERTEX_NAME,
  vertexIndexAttr: INDEX_ATTR,
  readCoords: (g) => g.coords,
  withCoords: (g, coords) => ({ ...g, coords }),
};

/** A group node as a renderer would stamp it; `x`/`y` are its drag offset. */
function fakeGroup(id: string, x = 0, y = 0) {
  let gx = x;
  let gy = y;
  return {
    name: () => "group",
    getAttr: (k: string) => (k === ID_ATTR ? id : undefined),
    getParent: () => null,
    x: (v?: number) => (v !== undefined ? (gx = v) : gx),
    y: (v?: number) => (v !== undefined ? (gy = v) : gy),
  };
}

/** A vertex handle, child of `parent`, dropped at stage pixel (x, y). */
function fakeVertex(parent: ReturnType<typeof fakeGroup>, index: number, x: number, y: number) {
  return {
    name: () => VERTEX_NAME,
    getAttr: (k: string) => (k === INDEX_ATTR ? index : undefined),
    getParent: () => parent,
    x: () => x,
    y: () => y,
  };
}

function makeHarness() {
  const collection = new AnnotationCollection();
  const handlers: Record<string, (e: { target: unknown }) => void> = {};
  // Held as standalone consts, not read back off `ctx.mutations`: asserting on
  // a mock through a property access trips eslint's `unbound-method` rule.
  const upsertUpdate = vi.fn();
  const patchPendingCreate = vi.fn();
  const off = vi.fn();
  const ctx = {
    widgetId: "w1",
    buildContext: { datasetId: "ds", recordId: "rec", viewId: "view-1" },
    collection,
    mutations: {
      pending: [],
      queue: vi.fn(),
      upsertUpdate,
      patchPendingCreate,
      dropForLocalAnnotation: vi.fn(),
      dropPendingEntityCreate: vi.fn(),
    },
    annotationLayer: {
      on: (evt: string, fn: (e: { target: unknown }) => void) => (handlers[evt] = fn),
      off,
    } as unknown as Konva.Layer,
    // A 100×100 frame at the origin, so pixels map to normalized /100.
    getKonvaImage: () =>
      ({ x: () => 0, y: () => 0, width: () => 100, height: () => 100 }) as unknown as Konva.Image,
    requestRedraw: vi.fn(),
  } as unknown as Scene2DContext;
  return { ctx, collection, handlers, upsertUpdate, patchPendingCreate, off };
}

function seed(collection: AnnotationCollection, persisted = true) {
  collection.add({
    id: "a1",
    entityId: "e1",
    kind: "multi_path",
    viewId: "view-1",
    geometry: {
      coords: [0.1, 0.1, 0.2, 0.2],
      numPoints: [2],
      isClosed: false,
    } as unknown as never,
    persisted,
  });
}

describe("flatCoordsEditor2D", () => {
  let harness: ReturnType<typeof makeHarness>;
  const drag = (target: unknown) => harness.handlers["dragend.multi_path-edit"]({ target });

  beforeEach(() => {
    harness = makeHarness();
    createFlatCoordsEditor2D(harness.ctx, spec);
  });

  it("moves only the dragged vertex and queues one update", () => {
    seed(harness.collection);
    const group = fakeGroup("a1");

    drag(fakeVertex(group, 1, 50, 60));

    expect(harness.collection.find("a1")?.geometry).toEqual({
      coords: [0.1, 0.1, 0.5, 0.6],
      numPoints: [2],
      isClosed: false,
    });
    expect(harness.upsertUpdate).toHaveBeenCalledTimes(1);
  });

  it("adds the group's offset to a vertex, since the handle is its child", () => {
    seed(harness.collection);
    // Group shifted +10px: a handle sitting at local 40 is really at 50.
    const group = fakeGroup("a1", 10, 10);

    drag(fakeVertex(group, 0, 40, 40));

    expect(harness.collection.find("a1")?.geometry).toMatchObject({
      coords: [0.5, 0.5, 0.2, 0.2],
    });
  });

  it("bakes a group drag into every point and zeroes the offset", () => {
    seed(harness.collection);
    const group = fakeGroup("a1", 10, -5);

    drag(group);

    // Compared loosely: shifting by a normalized delta is float arithmetic
    // (0.2 + 0.1 is not exactly 0.3), and the backend takes floats anyway.
    const coords = (harness.collection.find("a1")?.geometry as { coords: number[] }).coords;
    for (const [i, expected] of [0.2, 0.05, 0.3, 0.15].entries()) {
      expect(coords[i]).toBeCloseTo(expected, 10);
    }
    // Left non-zero, the next resync would draw the shape shifted twice.
    expect(group.x()).toBe(0);
    expect(group.y()).toBe(0);
  });

  it("clamps a drag past the media edge instead of dropping the edit", () => {
    seed(harness.collection);

    drag(fakeVertex(fakeGroup("a1"), 0, -40, 180));

    expect(harness.collection.find("a1")?.geometry).toMatchObject({
      coords: [0, 1, 0.2, 0.2],
    });
  });

  it("patches the pending create for an unsaved annotation", () => {
    seed(harness.collection, false);

    drag(fakeVertex(fakeGroup("a1"), 0, 50, 50));

    expect(harness.patchPendingCreate).toHaveBeenCalledTimes(1);
    expect(harness.upsertUpdate).not.toHaveBeenCalled();
  });

  it("ignores a group drag that did not move", () => {
    seed(harness.collection);

    drag(fakeGroup("a1"));

    expect(harness.upsertUpdate).not.toHaveBeenCalled();
  });

  it("ignores a node that carries no annotation id", () => {
    seed(harness.collection);

    drag(fakeGroup("unknown-id"));

    expect(harness.upsertUpdate).not.toHaveBeenCalled();
  });

  it("ignores a vertex whose index is past the coordinate list", () => {
    seed(harness.collection);

    drag(fakeVertex(fakeGroup("a1"), 99, 50, 50));

    expect(harness.collection.find("a1")?.geometry).toMatchObject({
      coords: [0.1, 0.1, 0.2, 0.2],
    });
    expect(harness.upsertUpdate).not.toHaveBeenCalled();
  });

  it("stops listening once destroyed", () => {
    const editor = createFlatCoordsEditor2D(harness.ctx, spec);
    editor.destroy();
    expect(harness.off).toHaveBeenCalledWith("dragend.multi_path-edit");
  });
});
