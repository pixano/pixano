/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { multiPathRenderer2DFactory } from "../multiPathRenderer2D.js";
import {
  MULTI_PATH_NODE_NAME,
  MULTI_PATH_VERTEX_INDEX_ATTR,
  MULTI_PATH_VERTEX_NAME,
  type MultiPathGeometry,
} from "../multiPathTypes.js";
import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { Scene2DReadContext } from "$lib/annotations/scene/sceneContext.js";

interface FakeNode {
  name?: string;
  attrs: Record<string, unknown>;
  cfg: Record<string, unknown>;
  children: FakeNode[];
}

const groups: FakeNode[] = [];

// Konva is faked down to what the renderer touches: a group that collects its
// children, and shapes that keep the config they were built with, so the test
// can assert on what was drawn rather than on how it looks.
vi.mock("konva", () => {
  class Node {
    attrs: Record<string, unknown> = {};
    children: FakeNode[] = [];
    destroyed = false;
    constructor(public cfg: Record<string, unknown> = {}) {}
    get name() {
      return this.cfg.name as string | undefined;
    }
    setAttr(key: string, value: unknown) {
      this.attrs[key] = value;
    }
    on() {}
    add(child: FakeNode) {
      this.children.push(child);
    }
    destroy() {
      this.destroyed = true;
    }
  }
  class Group extends Node {
    constructor(cfg: Record<string, unknown> = {}) {
      super(cfg);
      groups.push(this as unknown as FakeNode);
    }
  }
  return { default: { Group, Line: Node, Circle: Node } };
});

const TWO_RING_POLYGON: MultiPathGeometry = {
  // Two triangles, so vertex indexing has to cross a sub-path boundary.
  coords: [0.1, 0.1, 0.2, 0.1, 0.15, 0.2, 0.5, 0.5, 0.6, 0.5, 0.55, 0.6],
  numPoints: [3, 3],
  isClosed: true,
};

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
    id: "p1",
    entityId: "e1",
    kind: "multi_path",
    viewId: "v1",
    geometry: TWO_RING_POLYGON,
    persisted: true,
  });
  return { ctx, collection };
}

const vertices = (group: FakeNode) =>
  group.children.filter((c) => c.cfg.name === MULTI_PATH_VERTEX_NAME);
const lines = (group: FakeNode) =>
  group.children.filter((c) => c.cfg.name === MULTI_PATH_NODE_NAME);

describe("multiPathRenderer2D", () => {
  let harness: ReturnType<typeof makeHarness>;

  beforeEach(() => {
    groups.length = 0;
    harness = makeHarness();
  });

  it("draws no vertex handles while the path is unselected", () => {
    multiPathRenderer2DFactory.create(harness.ctx).sync();

    expect(lines(groups[0])).toHaveLength(2); // one per ring
    // A saved shape should read as a clean outline, like a bbox without its
    // transformer — the dots belong to editing, not to display.
    expect(vertices(groups[0])).toHaveLength(0);
  });

  it("draws one handle per point once selected", () => {
    harness.collection.select("p1");
    multiPathRenderer2DFactory.create(harness.ctx).sync();

    expect(vertices(groups[0])).toHaveLength(6);
  });

  it("numbers handles continuously across sub-paths", () => {
    harness.collection.select("p1");
    multiPathRenderer2DFactory.create(harness.ctx).sync();

    // Ring 2's handles must continue where ring 1 stopped: the index addresses
    // the flat `coords` list, so restarting at 0 would edit the wrong point.
    expect(vertices(groups[0]).map((v) => v.attrs[MULTI_PATH_VERTEX_INDEX_ATTR])).toEqual([
      0, 1, 2, 3, 4, 5,
    ]);
  });

  it("thickens the outline when selected, so selection is visible without handles", () => {
    multiPathRenderer2DFactory.create(harness.ctx).sync();
    const idle = lines(groups[0])[0].cfg.strokeWidth as number;

    groups.length = 0;
    harness.collection.select("p1");
    multiPathRenderer2DFactory.create(harness.ctx).sync();
    const selected = lines(groups[0])[0].cfg.strokeWidth as number;

    expect(selected).toBeGreaterThan(idle);
  });

  it("gives the outline a hit width, so a handle-less path stays clickable", () => {
    multiPathRenderer2DFactory.create(harness.ctx).sync();

    // With the dots hidden, an open polyline would otherwise be a 2px thread.
    expect(lines(groups[0])[0].cfg.hitStrokeWidth).toBeGreaterThan(2);
  });
});
