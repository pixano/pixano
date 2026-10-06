/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { bboxRenderer2DFactory } from "../bboxRenderer2D.js";
import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { Scene2DReadContext } from "$lib/annotations/scene/sceneContext.js";

interface FakeNode {
  attrs: Record<string, unknown>;
  cfg: Record<string, unknown>;
  children: FakeNode[];
  destroyed: boolean;
}

const labels: FakeNode[] = [];

vi.mock("konva", () => {
  class Node {
    attrs: Record<string, unknown> = {};
    children: FakeNode[] = [];
    destroyed = false;
    constructor(public cfg: Record<string, unknown> = {}) {}
    setAttr(key: string, value: unknown) {
      this.attrs[key] = value;
    }
    getAttr(key: string) {
      return this.attrs[key];
    }
    on() {}
    add(child: FakeNode) {
      this.children.push(child);
    }
    _pos = { x: 0, y: 0 };
    position(value?: { x: number; y: number }) {
      if (value) this._pos = value;
      return this._pos;
    }
    width() {
      return 10;
    }
    height() {
      return 10;
    }
    stroke() {}
    dash() {}
    x() {
      return 0;
    }
    y() {
      return 0;
    }
    destroy() {
      this.destroyed = true;
    }
  }
  class Label extends Node {
    constructor(cfg: Record<string, unknown> = {}) {
      super(cfg);
      labels.push(this as unknown as FakeNode);
    }
  }
  return { default: { Label, Rect: Node, Tag: Node, Text: Node } };
});

/** The text a label ended up showing, read off its Konva.Text child. */
const textOf = (label: FakeNode) =>
  label.children.map((c) => c.cfg.text).find((t) => t !== undefined);

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
    id: "b1",
    entityId: "e1",
    kind: "bbox",
    viewId: "v1",
    geometry: [0.1, 0.1, 0.2, 0.2],
    persisted: true,
    entity: { id: "e1", name: "dog" },
  });
  return { ctx, collection };
}

describe("bboxRenderer2D", () => {
  let harness: ReturnType<typeof makeHarness>;

  beforeEach(() => {
    labels.length = 0;
    harness = makeHarness();
  });

  it("names the entity the box belongs to", () => {
    bboxRenderer2DFactory.create(harness.ctx).sync();

    expect(textOf(labels[0])).toBe("dog");
  });

  it("renames the label when the box is moved to another entity", () => {
    const renderer = bboxRenderer2DFactory.create(harness.ctx);
    renderer.sync();

    harness.collection.setEntity("b1", "e2", { id: "e2", name: "cat" });
    renderer.sync();

    // Built once and never revisited, the label went on naming the entity the
    // box had left — visible for a whole session, until a page reload.
    expect(labels[0].destroyed).toBe(true);
    expect(textOf(labels.at(-1)!)).toBe("cat");
  });

  it("keeps the same label node when the entity did not change", () => {
    const renderer = bboxRenderer2DFactory.create(harness.ctx);
    renderer.sync();
    renderer.sync();

    // sync() runs on every collection change; rebuilding a label each time
    // would churn nodes for a neighbouring annotation's move.
    expect(labels).toHaveLength(1);
    expect(labels[0].destroyed).toBe(false);
  });
});
