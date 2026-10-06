/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { keypointsRenderer2DFactory } from "../keypointsRenderer2D.js";
import {
  KEYPOINTS_EDGE_NAME,
  KEYPOINTS_VERTEX_INDEX_ATTR,
  KEYPOINTS_VERTEX_NAME,
  type KeypointsGeometry,
} from "../keypointsTypes.js";
import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { Scene2DReadContext } from "$lib/annotations/scene/sceneContext.js";

interface FakeNode {
  attrs: Record<string, unknown>;
  cfg: Record<string, unknown>;
  children: FakeNode[];
}

const groups: FakeNode[] = [];

vi.mock("konva", () => {
  class Node {
    attrs: Record<string, unknown> = {};
    children: FakeNode[] = [];
    constructor(public cfg: Record<string, unknown> = {}) {}
    setAttr(key: string, value: unknown) {
      this.attrs[key] = value;
    }
    getAttr(key: string) {
      return this.attrs[key];
    }
    x() {
      return (this.cfg.x as number) ?? 0;
    }
    y() {
      return (this.cfg.y as number) ?? 0;
    }
    position() {}
    height() {
      return 0;
    }
    on() {}
    add(child: FakeNode) {
      this.children.push(child);
    }
    destroy() {}
  }
  class Group extends Node {
    constructor(cfg: Record<string, unknown> = {}) {
      super(cfg);
      groups.push(this as unknown as FakeNode);
    }
  }
  return { default: { Group, Line: Node, Circle: Node, Label: Node, Tag: Node, Text: Node } };
});

/** The "face" template: eye left, eye right, nose, mouth. */
function faceGeometry(states: KeypointsGeometry["states"]): KeypointsGeometry {
  return {
    templateId: "face",
    coords: [0.1, 0.1, 0.3, 0.1, 0.2, 0.2, 0.2, 0.3],
    states,
  };
}

function makeHarness(geometry: KeypointsGeometry) {
  const collection = new AnnotationCollection();
  const ctx = {
    collection,
    annotationLayer: { add: vi.fn(), batchDraw: vi.fn() } as unknown as Konva.Layer,
    getKonvaImage: () =>
      ({ x: () => 0, y: () => 0, width: () => 100, height: () => 100 }) as unknown as Konva.Image,
    isEntityVisible: () => true,
  } as unknown as Scene2DReadContext;
  collection.add({
    id: "k1",
    entityId: "e1",
    kind: "keypoints",
    viewId: "v1",
    geometry,
    persisted: true,
  });
  return { ctx, collection };
}

const vertices = (group: FakeNode) =>
  group.children.filter((c) => c.cfg.name === KEYPOINTS_VERTEX_NAME);
const edges = (group: FakeNode) => group.children.filter((c) => c.cfg.name === KEYPOINTS_EDGE_NAME);

describe("keypointsRenderer2D", () => {
  beforeEach(() => {
    groups.length = 0;
  });

  it("stamps a handle with its point index, not its rank among drawn circles", () => {
    // The second point is hidden, so it gets no circle: the third point is the
    // second circle drawn but is still index 2 in `coords`. Confusing the two
    // would drag the wrong keypoint.
    const harness = makeHarness(faceGeometry(["visible", "hidden", "visible", "visible"]));
    harness.collection.select("k1");
    keypointsRenderer2DFactory.create(harness.ctx).sync();

    expect(vertices(groups[0]).map((v) => v.attrs[KEYPOINTS_VERTEX_INDEX_ATTR])).toEqual([0, 2, 3]);
  });

  it("keeps every annotated point visible, selected or not", () => {
    // Unlike a path's handles, these circles *are* the annotation — hiding them
    // would leave bones floating without their joints.
    const harness = makeHarness(faceGeometry(["visible", "visible", "visible", "visible"]));
    keypointsRenderer2DFactory.create(harness.ctx).sync();

    expect(vertices(groups[0])).toHaveLength(4);
  });

  it("makes the bones grabbable, so the whole skeleton can still be moved", () => {
    // Bones are the only non-vertex part of a skeleton. Deaf, they left the
    // group catchable only through a handle — and a selected handle drags
    // itself, which silently removed any way to move the skeleton as a whole.
    const harness = makeHarness(faceGeometry(["visible", "visible", "visible", "visible"]));
    harness.collection.select("k1");
    keypointsRenderer2DFactory.create(harness.ctx).sync();

    const bone = edges(groups[0])[0];
    expect(bone.cfg.listening).not.toBe(false);
    expect(bone.cfg.hitStrokeWidth).toBeGreaterThan(0);
  });

  it("thickens the bones when selected", () => {
    const idleHarness = makeHarness(faceGeometry(["visible", "visible", "visible", "visible"]));
    keypointsRenderer2DFactory.create(idleHarness.ctx).sync();
    const idle = edges(groups[0])[0].cfg.strokeWidth as number;

    groups.length = 0;
    const selectedHarness = makeHarness(faceGeometry(["visible", "visible", "visible", "visible"]));
    selectedHarness.collection.select("k1");
    keypointsRenderer2DFactory.create(selectedHarness.ctx).sync();

    expect(edges(groups[0])[0].cfg.strokeWidth as number).toBeGreaterThan(idle);
  });

  it("exposes draggable handles only on the selected skeleton", () => {
    const harness = makeHarness(faceGeometry(["visible", "visible", "visible", "visible"]));
    keypointsRenderer2DFactory.create(harness.ctx).sync();

    expect(vertices(groups[0]).every((v) => v.cfg.draggable === false)).toBe(true);
  });
});
