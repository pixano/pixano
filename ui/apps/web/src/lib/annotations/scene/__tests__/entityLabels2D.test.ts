/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LocalAnnotation } from "../../annotationCollection.svelte.js";
import { EntityLabels2D } from "../entityLabels2D.js";
import { BBOX_COLOR_PERSISTED } from "../scene2dStyleConstants.js";

interface FakeNode {
  attrs: Record<string, unknown>;
  cfg: Record<string, unknown>;
  children: FakeNode[];
  destroyed: boolean;
}

const labels: FakeNode[] = [];

// Konva needs a real canvas to measure text; the label logic under test is the
// reconciliation, so a node that records its config is enough.
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
    add(child: FakeNode) {
      this.children.push(child);
    }
    position() {}
    height() {
      return 10;
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
  return { default: { Label, Tag: Node, Text: Node } };
});

const fillOf = (label: FakeNode) =>
  label.children.map((c) => c.cfg.fill).find((f) => f !== undefined);
const live = () => labels.filter((l) => !l.destroyed);

function annotation(overrides: Partial<LocalAnnotation> = {}): LocalAnnotation {
  return {
    id: "a1",
    entityId: "e1",
    kind: "bbox",
    viewId: "v",
    geometry: [0, 0, 1, 1],
    persisted: true,
    entity: { id: "e1", category: "car" },
    ...overrides,
  };
}

function makeLabels() {
  const layer = { add: vi.fn() } as unknown as Konva.Layer;
  return new EntityLabels2D(layer);
}

const ANCHOR = { x: 0, y: 0 };

beforeEach(() => {
  labels.length = 0;
});

describe("EntityLabels2D", () => {
  it("recolours a draft's label once it is saved", () => {
    const entityLabels = makeLabels();
    entityLabels.sync([{ id: "a1", annotation: annotation({ persisted: false }), anchor: ANCHOR }]);

    entityLabels.sync([{ id: "a1", annotation: annotation({ persisted: true }), anchor: ANCHOR }]);

    expect(live()).toHaveLength(1);
    expect(fillOf(live()[0])).toBe(BBOX_COLOR_PERSISTED);
  });
});
