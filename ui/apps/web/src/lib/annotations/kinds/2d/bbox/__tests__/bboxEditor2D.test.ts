/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BBOX_RESOURCE } from "../bboxPayloadBuilder.js";
import { bboxRenderer2DFactory } from "../bboxRenderer2D.js";
import type { BBoxGeometry } from "$lib/annotations/annotationCollection.svelte.js";
import { commitNewAnnotation } from "$lib/annotations/payloadBuilders.js";
import { installSilentCanvas } from "$lib/annotations/scene/__tests__/konvaInHappyDom.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import {
  humanBox,
  openManager,
  widgetSeam,
  type Row,
} from "$lib/workspace/__tests__/workspaceHarness.js";

// The editor runs on the real Konva, over the real workspace: a mocked Konva
// answers whatever the mock says, and that is how a resize went unsaved — the
// old test called a layer handler Konva never calls (a resize's end does not
// bubble). Konva's browser build, as the app loads it (see konvaInHappyDom.ts).
vi.mock("konva", async () => ({
  default: (await vi.importActual<{ default: unknown }>("konva/lib/index.js")).default,
}));

installSilentCanvas();

const REC = "rec-1";
/** The displayed image: 100 × 100 px at the stage origin, so 1 px is 0.01 of the image. */
const IMAGE_PIXELS = 100;
const STAGE_PIXELS = 200;
/** How close a coordinate read back through pixels lands to what was meant. */
const COORDS_DIGITS = 6;

/** A person's box at [0.1, 0.1, 0.2, 0.2]: drawn 20 × 20 px at (10, 10). */
const BOX = humanBox(REC, "b1");

afterEach(() => {
  // Konva's drags are global: one a failed test left running would move with
  // the next test's pointer. Let go of it, so each test starts with none.
  window.dispatchEvent(new MouseEvent("mouseup"));
  document.body.innerHTML = "";
});

/**
 * The record open on a real stage, with the bbox renderer and editor the image
 * widget wires.
 *
 * @param box The box the record holds: a person's unless told otherwise.
 */
async function openOnCanvas(box: Row = BOX) {
  const opened = await openManager({ [REC]: { [BBOX_RESOURCE]: [box] } });
  const container = document.createElement("div");
  document.body.appendChild(container);
  const stage = new Konva.Stage({ container, width: STAGE_PIXELS, height: STAGE_PIXELS });
  const layer = new Konva.Layer();
  stage.add(layer);
  const image = new Konva.Image({
    image: undefined,
    x: 0,
    y: 0,
    width: IMAGE_PIXELS,
    height: IMAGE_PIXELS,
  });
  layer.add(image);
  const seam = widgetSeam(opened.manager);
  const ctx: Scene2DContext = {
    ...seam,
    stage,
    annotationLayer: layer,
    getKonvaImage: () => image,
    camera: { imageWidth: IMAGE_PIXELS, imageHeight: IMAGE_PIXELS, calibration: null },
    // What the image widget's redraw hook does: the renderer, then the editor.
    requestRedraw: () => redraw(),
  };
  const renderer = bboxRenderer2DFactory.create(ctx);
  const editor = bboxRenderer2DFactory.createEditor!(ctx);
  function redraw(): void {
    renderer.sync();
    editor.syncSelection();
  }
  redraw();
  return { ...opened, ctx, stage, layer, renderer, editor, redraw };
}

type OnCanvas = Awaited<ReturnType<typeof openOnCanvas>>;

function rectOf(scene: OnCanvas, id: string): Konva.Rect {
  const rect = scene.layer.find<Konva.Rect>(".bbox").find((node) => node.getAttr("bboxId") === id);
  if (!rect) throw new Error(`no rect for ${id}`);
  return rect;
}

/** Select a box as a click does, so the transformer takes hold of it. */
function select(scene: OnCanvas, id: string): void {
  scene.ctx.collection.select(id);
  scene.redraw();
}

/** A resize handle of the transformer, by the name Konva gives it. */
type Handle =
  | "top-left"
  | "top-center"
  | "top-right"
  | "middle-left"
  | "middle-right"
  | "bottom-left"
  | "bottom-center"
  | "bottom-right";

/** How many moves a pointer drag is made of: a mouse reports a drag in steps, not in one jump. */
const DRAG_STEPS = 8;

/**
 * Press a mouse on a node: Konva's own drag takes it from there.
 *
 * @returns `moveTo` takes the pointer, in steps, to (dx, dy) px from where the
 *   node was pressed; `release` lets go there.
 */
function grab(scene: OnCanvas, node: Konva.Node) {
  const from = node.getAbsolutePosition();
  const down = new MouseEvent("mousedown", { clientX: from.x, clientY: from.y, bubbles: true });
  scene.stage.setPointersPositions(down);
  node.fire("mousedown", { evt: down, target: node });
  let at = { dx: 0, dy: 0 };
  return {
    moveTo(dx: number, dy: number): void {
      for (let step = 1; step <= DRAG_STEPS; step++) {
        const x = at.dx + ((dx - at.dx) * step) / DRAG_STEPS;
        const y = at.dy + ((dy - at.dy) * step) / DRAG_STEPS;
        window.dispatchEvent(
          new MouseEvent("mousemove", { clientX: from.x + x, clientY: from.y + y }),
        );
      }
      at = { dx, dy };
    },
    release(): void {
      window.dispatchEvent(
        new MouseEvent("mouseup", { clientX: from.x + at.dx, clientY: from.y + at.dy }),
      );
    },
  };
}

/** Grab a handle of the selected box's transformer, as a mouse press does (see `grab`). */
function grabHandle(scene: OnCanvas, handle: Handle) {
  const transformer = scene.layer.findOne<Konva.Transformer>("Transformer");
  const anchor = transformer?.findOne<Konva.Rect>(`.${handle}`);
  if (!anchor) throw new Error(`no ${handle} handle on the selected box`);
  return grab(scene, anchor);
}

/** Drag a handle of the selected box by (dx, dy) px and let go, as a mouse does. */
function resizeFrom(scene: OnCanvas, handle: Handle, dx: number, dy: number): void {
  const grabbed = grabHandle(scene, handle);
  grabbed.moveTo(dx, dy);
  grabbed.release();
}

/** Drag the transformer's bottom-right handle by (dx, dy) px, as a mouse does. */
function resizeFromBottomRight(scene: OnCanvas, dx: number, dy: number): void {
  resizeFrom(scene, "bottom-right", dx, dy);
}

/** Drag a node by (dx, dy) px through Konva's own drag, as a mouse does. */
function dragBy(scene: OnCanvas, node: Konva.Rect, dx: number, dy: number): void {
  const from = node.getAbsolutePosition();
  scene.stage.setPointersPositions(
    new MouseEvent("mousedown", { clientX: from.x, clientY: from.y }),
  );
  node.startDrag();
  const to = { clientX: from.x + dx, clientY: from.y + dy };
  window.dispatchEvent(new MouseEvent("mousemove", to));
  window.dispatchEvent(new MouseEvent("mouseup", to));
}

function expectCoords(actual: unknown, expected: number[]): void {
  expect(actual).toHaveLength(expected.length);
  (actual as number[]).forEach((value, index) =>
    expect(value).toBeCloseTo(expected[index], COORDS_DIGITS),
  );
}

/**
 * Expect a box the server takes: every coordinate in [0, 1], the box inside
 * the image (x + w ≤ 1, y + h ≤ 1), and an edge meant to lie on the image's
 * left or top border exactly on it — not a hair past it, which the server's
 * validator refuses.
 */
function expectInsideTheImage(coords: unknown, expected: number[]): void {
  expectCoords(coords, expected);
  const [x, y, w, h] = coords as number[];
  for (const value of [x, y, w, h]) {
    expect(value).toBeGreaterThanOrEqual(0);
    expect(value).toBeLessThanOrEqual(1);
  }
  expect(x + w).toBeLessThanOrEqual(1);
  expect(y + h).toBeLessThanOrEqual(1);
  if (expected[0] === 0) expect(x).toBe(0);
  if (expected[1] === 0) expect(y).toBe(0);
}

/** The coordinates of the update queued for the record, if any. */
function queuedCoords(scene: OnCanvas): unknown {
  const update = scene.manager.pendingMutations.find((m) => m.op === "update");
  return update?.op === "update" ? update.body.coords : undefined;
}

describe("bboxEditor2D on the real Konva", () => {
  it("saves a box resized with the transformer's handle", async () => {
    const scene = await openOnCanvas();
    select(scene, "b1");

    resizeFromBottomRight(scene, 20, 20);

    // 20 × 20 px grown to 40 × 40 px: the geometry, the queued update and the
    // node all hold the new size, the scale baked in.
    expectCoords(scene.ctx.collection.find("b1")?.geometry, [0.1, 0.1, 0.4, 0.4]);
    const update = scene.manager.pendingMutations.find((m) => m.op === "update");
    expectCoords(update?.op === "update" ? update.body.coords : undefined, [0.1, 0.1, 0.4, 0.4]);
    const rect = rectOf(scene, "b1");
    expect([rect.scaleX(), rect.scaleY()]).toEqual([1, 1]);
    expect(rect.width()).toBeCloseTo(40, COORDS_DIGITS);
  });

  it("patches the pending create of a draft resized before its save", async () => {
    const scene = await openOnCanvas();
    const draft = commitNewAnnotation<BBoxGeometry>(scene.ctx, "bbox", [0.5, 0.5, 0.1, 0.1]);
    select(scene, draft.id);

    resizeFromBottomRight(scene, 10, 10);

    const create = scene.manager.pendingMutations.find(
      (m) => m.op === "create" && m.resource === BBOX_RESOURCE,
    );
    expectCoords(create?.op === "create" ? create.body.coords : undefined, [0.5, 0.5, 0.2, 0.2]);
    expect(scene.manager.pendingMutations.some((m) => m.op === "update")).toBe(false);
  });

  it("saves a dragged box", async () => {
    const scene = await openOnCanvas();

    dragBy(scene, rectOf(scene, "b1"), 10, 0);

    expectCoords(scene.ctx.collection.find("b1")?.geometry, [0.2, 0.1, 0.2, 0.2]);
    expect(scene.manager.pendingMutations).toHaveLength(1);
  });

  it("ignores the drag of a node that is not a box", async () => {
    const scene = await openOnCanvas();
    const other = new Konva.Rect({
      x: 0,
      y: 0,
      width: 5,
      height: 5,
      name: "other",
      draggable: true,
    });
    scene.layer.add(other);

    dragBy(scene, other, 10, 10);

    expect(scene.manager.pendingMutations).toHaveLength(0);
  });

  it("stops listening once destroyed", async () => {
    const scene = await openOnCanvas();
    select(scene, "b1");
    scene.editor.destroy();

    dragBy(scene, rectOf(scene, "b1"), 10, 0);

    expect(scene.manager.pendingMutations).toHaveLength(0);
  });
});

describe("bboxEditor2D, a box taken past the image's edge", () => {
  // The box is drawn 20 × 20 px at (10, 10); the image spans 0..100 px.

  it("keeps a box dragged past the left and top edges whole, against them", async () => {
    const scene = await openOnCanvas();

    dragBy(scene, rectOf(scene, "b1"), -25, -15);

    expectInsideTheImage(queuedCoords(scene), [0, 0, 0.2, 0.2]);
    expectCoords(scene.ctx.collection.find("b1")?.geometry, [0, 0, 0.2, 0.2]);
    // Drawn where it is saved, not where the pointer let go of it.
    expect([rectOf(scene, "b1").x(), rectOf(scene, "b1").y()]).toEqual([0, 0]);
  });

  it("keeps a box dragged past the right and bottom edges whole, against them", async () => {
    const scene = await openOnCanvas();

    dragBy(scene, rectOf(scene, "b1"), 85, 95);

    expectInsideTheImage(queuedCoords(scene), [0.8, 0.8, 0.2, 0.2]);
    expect(rectOf(scene, "b1").x()).toBeCloseTo(80, COORDS_DIGITS);
  });

  it("cuts a box resized past the left and top edges at them", async () => {
    const scene = await openOnCanvas();
    select(scene, "b1");

    resizeFrom(scene, "top-left", -25, -25);

    // From (-15, -15) to (30, 30) px: what lies past the edges is not the image's.
    expectInsideTheImage(queuedCoords(scene), [0, 0, 0.3, 0.3]);
    const rect = rectOf(scene, "b1");
    expect([rect.x(), rect.y()]).toEqual([0, 0]);
    expect(rect.width()).toBeCloseTo(30, COORDS_DIGITS);
  });

  it("cuts a box resized past the right and bottom edges at them", async () => {
    const scene = await openOnCanvas();
    select(scene, "b1");

    resizeFrom(scene, "bottom-right", 90, 90);

    expectInsideTheImage(queuedCoords(scene), [0.1, 0.1, 0.9, 0.9]);
    expect(rectOf(scene, "b1").width()).toBeCloseTo(90, COORDS_DIGITS);
  });

  it("sends the server a box it takes, once saved", async () => {
    const scene = await openOnCanvas();

    dragBy(scene, rectOf(scene, "b1"), -25, -15);
    await scene.manager.flushSave();

    expect(scene.manager.saveError).toBeNull();
    const sent = scene.backend.writes.find((w) => w.op === "update");
    expectInsideTheImage(sent?.op === "update" ? sent.body.coords : undefined, [0, 0, 0.2, 0.2]);
  });
});

describe("bboxEditor2D, a box stored with no width", () => {
  // Saved so before the cut kept the least size, or imported so. Konva scales
  // a box by dividing by its size, and leaves the node of one with no width
  // with no number for its place or its size.

  it("commits nothing for a resize, which Konva cannot make, and draws the box as stored", async () => {
    const stored = [0.5, 0.1, 0, 0.2];
    const scene = await openOnCanvas({ ...humanBox(REC, "h1"), coords: stored });
    select(scene, "h1");

    resizeFrom(scene, "middle-right", 20, 0);

    expect(queuedCoords(scene)).toBeUndefined();
    expectCoords(scene.ctx.collection.find("h1")?.geometry, stored);
    const rect = rectOf(scene, "h1");
    expectCoords(
      [rect.x(), rect.y(), rect.width(), rect.height()],
      stored.map((value) => value * IMAGE_PIXELS),
    );
  });
});

describe("bboxRenderer2D on the real Konva", () => {
  it("draws a box at the size the collection holds, whatever transform was left on its node", async () => {
    const scene = await openOnCanvas();
    const rect = rectOf(scene, "b1");
    // A transform the editor never baked — the state an unsaved resize used to
    // leave — and the half turn Konva records a flipped box with.
    rect.scale({ x: 2, y: 2 });
    rect.rotation(-180);

    scene.renderer.sync();

    expect([rect.rotation(), rect.scaleX(), rect.scaleY()]).toEqual([0, 1, 1]);
    expect([rect.width(), rect.height()]).toEqual([20, 20]);
  });
});
