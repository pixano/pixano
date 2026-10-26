/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BBOX_DRAGGING_ATTR } from "../bbox2dNodes.js";
import { BBOX_RESOURCE } from "../bboxPayloadBuilder.js";
import { bboxRenderer2DFactory } from "../bboxRenderer2D.js";
import type { BBoxGeometry } from "$lib/annotations/annotationCollection.svelte.js";
import { commitGeometryEdit, commitNewAnnotation } from "$lib/annotations/payloadBuilders.js";
import { installSilentCanvas } from "$lib/annotations/scene/__tests__/konvaInHappyDom.js";
import type { Scene2DContext, StagedWorkFlag } from "$lib/annotations/scene/sceneContext.js";
import { selectTool2D } from "$lib/annotations/scene/selectTool2D.js";
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
/** Another of the person's boxes, at [0.6, 0.6, 0.2, 0.2]: clear of the first. */
const OTHER_BOX: Row = { ...humanBox(REC, "b2"), coords: [0.6, 0.6, 0.2, 0.2] };

afterEach(() => {
  // Konva's drags are global: one a failed test left running would move with
  // the next test's pointer. Let go of it, so each test starts with none.
  window.dispatchEvent(new MouseEvent("mouseup"));
  document.body.innerHTML = "";
});

/**
 * The record open on a real stage, with the bbox renderer and editor the image
 * widget wires, and the select tool the widget hands its keys to.
 *
 * @param box The box the record holds: a person's unless told otherwise.
 * @param others More boxes the record holds.
 */
async function openOnCanvas(box: Row = BOX, ...others: Row[]) {
  const opened = await openManager({ [REC]: { [BBOX_RESOURCE]: [box, ...others] } });
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
  /** Every value the editor set its staged-work flag to, in order. */
  const flagSets: boolean[] = [];
  const ctx: Scene2DContext = {
    ...seam,
    // The widget's own flag, with each value it is set to written down.
    claimStagedWork: (discard) => {
      const flag = seam.claimStagedWork!(discard);
      const recorded: StagedWorkFlag = {
        set: (staged) => {
          flagSets.push(staged);
          flag.set(staged);
        },
      };
      return recorded;
    },
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
  const selectTool = selectTool2D.createHandler(ctx);
  return { ...opened, ctx, stage, layer, renderer, editor, redraw, flagSets, selectTool };
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

/**
 * A person's edit of `OTHER_BOX`, queued as the editor commits a gesture's end:
 * something for the next save to send.
 */
function editOtherBox(scene: OnCanvas): void {
  commitGeometryEdit(scene.ctx, OTHER_BOX.id, [0.7, 0.6, 0.2, 0.2]);
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
    // Nor is it work the editor holds.
    expect(scene.flagSets).toEqual([]);
  });

  it("stops listening once destroyed", async () => {
    const scene = await openOnCanvas();
    select(scene, "b1");
    scene.editor.destroy();

    dragBy(scene, rectOf(scene, "b1"), 10, 0);

    expect(scene.manager.pendingMutations).toHaveLength(0);
  });
});

describe("bboxEditor2D, a handle dragged past the opposite edge", () => {
  // The box is drawn at 10..30 px on both axes. Each handle is dragged 10 px
  // past the opposite edge: the box spans from the edge that stays to the
  // pointer — 10 px on the axis the handle crossed — never a flipped node,
  // which Konva records as a negative scale or a half turn that no box holds.
  const PAST_THE_OPPOSITE_EDGE: [Handle, number, number, number[]][] = [
    ["top-left", 30, 30, [0.3, 0.3, 0.1, 0.1]],
    ["top-center", 0, 30, [0.1, 0.3, 0.2, 0.1]],
    ["top-right", -30, 30, [0, 0.3, 0.1, 0.1]],
    ["middle-left", 30, 0, [0.3, 0.1, 0.1, 0.2]],
    ["middle-right", -30, 0, [0, 0.1, 0.1, 0.2]],
    ["bottom-left", 30, -30, [0.3, 0, 0.1, 0.1]],
    ["bottom-center", 0, -30, [0.1, 0, 0.2, 0.1]],
    ["bottom-right", -30, -30, [0, 0, 0.1, 0.1]],
  ];

  it.each(PAST_THE_OPPOSITE_EDGE)(
    "%s: saves the box between the edge that stays and the pointer, and draws it there",
    async (handle, dx, dy, expected) => {
      const scene = await openOnCanvas();
      select(scene, "b1");

      resizeFrom(scene, handle, dx, dy);

      expectCoords(scene.ctx.collection.find("b1")?.geometry, expected);
      // Queued as the server takes it: a handle let go on the image's edge
      // puts the box's edge on it, not a float's error past it.
      expectInsideTheImage(queuedCoords(scene), expected);
      const rect = rectOf(scene, "b1");
      expect([rect.rotation(), rect.scaleX(), rect.scaleY()]).toEqual([0, 1, 1]);
      // Drawn where the collection holds it, and still there once the scene syncs.
      scene.redraw();
      const drawn = rect.getClientRect({ skipStroke: true });
      expectCoords(
        [drawn.x, drawn.y, drawn.width, drawn.height],
        expected.map((value) => value * IMAGE_PIXELS),
      );
    },
  );
});

describe("bboxEditor2D, a resize still running when a save ends", () => {
  it("is not put back by the save: it is saved once the handle is let go", async () => {
    const scene = await openOnCanvas(BOX, OTHER_BOX);
    // Something for the save to send.
    editOtherBox(scene);
    select(scene, "b1");
    const grabbed = grabHandle(scene, "bottom-right");
    grabbed.moveTo(10, 10);

    // The resize is the record's unsaved work until it ends.
    expect(scene.manager.hasUnsavedWork).toBe(true);
    expect(await scene.manager.flushSave()).toBe(false);
    // A save ends by clearing the selection, and the widget syncs its scene then.
    scene.redraw();
    grabbed.moveTo(20, 20);
    grabbed.release();

    // 20 × 20 px grown to 40 × 40 px, as when no save ran.
    expectCoords(scene.ctx.collection.find("b1")?.geometry, [0.1, 0.1, 0.4, 0.4]);
    const update = scene.manager.pendingMutations.find((m) => m.op === "update");
    expectCoords(update?.op === "update" ? update.body.coords : undefined, [0.1, 0.1, 0.4, 0.4]);
    const rect = rectOf(scene, "b1");
    expect([rect.scaleX(), rect.scaleY()]).toEqual([1, 1]);
    expect(rect.width()).toBeCloseTo(40, COORDS_DIGITS);
    // The save left nothing selected: the handles go once the resize is over.
    expect(scene.layer.findOne<Konva.Transformer>("Transformer")?.nodes()).toEqual([]);
  });

  it("is saved as it stood when the handle is let go right as the save ends", async () => {
    const scene = await openOnCanvas();
    select(scene, "b1");
    const grabbed = grabHandle(scene, "bottom-right");
    grabbed.moveTo(10, 10);

    await scene.manager.flushSave();
    scene.redraw();
    // Let go where it was: no later move puts the new size back on the box.
    grabbed.release();

    // 20 × 20 px grown to 30 × 30 px.
    expectCoords(scene.ctx.collection.find("b1")?.geometry, [0.1, 0.1, 0.3, 0.3]);
    expect(rectOf(scene, "b1").width()).toBeCloseTo(30, COORDS_DIGITS);
  });

  it("is dropped by Discard, and the box goes back as stored", async () => {
    const scene = await openOnCanvas();
    select(scene, "b1");
    const grabbed = grabHandle(scene, "bottom-right");
    grabbed.moveTo(10, 10);

    await scene.manager.discardChanges();
    grabbed.moveTo(20, 20);
    grabbed.release();

    expect(scene.manager.hasUnsavedWork).toBe(false);
    expect(scene.manager.pendingMutations).toEqual([]);
    expectCoords(scene.ctx.collection.find("b1")?.geometry, [0.1, 0.1, 0.2, 0.2]);
    const rect = rectOf(scene, "b1");
    expect([rect.scaleX(), rect.scaleY()]).toEqual([1, 1]);
    expect([rect.width(), rect.height()]).toEqual([20, 20]);
  });
});

describe("bboxEditor2D, a drag still running when a save ends", () => {
  // The box is drawn 20 × 20 px at (10, 10); each drag below moves it right.

  it("holds the box as unsaved work from dragstart to dragend, raising the flag once", async () => {
    const scene = await openOnCanvas();
    const grabbed = grab(scene, rectOf(scene, "b1"));

    grabbed.moveTo(10, 0);
    grabbed.moveTo(20, 0);

    // Raised as the drag began, not again at each of the pointer's moves.
    expect(scene.flagSets).toEqual([true]);
    expect(scene.manager.hasUnsavedWork).toBe(true);
    expect(rectOf(scene, "b1").getAttr(BBOX_DRAGGING_ATTR)).toBe(true);
    grabbed.release();

    expect(scene.flagSets).toEqual([true, false]);
    expect(rectOf(scene, "b1").getAttr(BBOX_DRAGGING_ATTR)).toBe(false);
    expectCoords(scene.ctx.collection.find("b1")?.geometry, [0.3, 0.1, 0.2, 0.2]);
    expect(scene.manager.pendingMutations.map((m) => m.op)).toEqual(["update"]);
  });

  it("is not put back by the save: it is saved once let go", async () => {
    const scene = await openOnCanvas(BOX, OTHER_BOX);
    // Something for the save to send.
    editOtherBox(scene);
    const grabbed = grab(scene, rectOf(scene, "b1"));
    grabbed.moveTo(10, 0);

    expect(await scene.manager.flushSave()).toBe(false);
    // A save ends by clearing the selection, and the widget syncs its scene then.
    scene.redraw();
    expect(rectOf(scene, "b1").x()).toBeCloseTo(20, COORDS_DIGITS);
    grabbed.moveTo(20, 0);
    grabbed.release();

    expectCoords(scene.ctx.collection.find("b1")?.geometry, [0.3, 0.1, 0.2, 0.2]);
    const update = scene.manager.pendingMutations.find((m) => m.op === "update");
    expectCoords(update?.op === "update" ? update.body.coords : undefined, [0.3, 0.1, 0.2, 0.2]);
  });

  it("is saved where it stood when let go right as the save ends", async () => {
    const scene = await openOnCanvas(BOX, OTHER_BOX);
    editOtherBox(scene);
    const grabbed = grab(scene, rectOf(scene, "b1"));
    grabbed.moveTo(10, 0);

    await scene.manager.flushSave();
    scene.redraw();
    // Let go where it was: no later move puts the box back where it was dragged.
    grabbed.release();

    expectCoords(scene.ctx.collection.find("b1")?.geometry, [0.2, 0.1, 0.2, 0.2]);
    expect(rectOf(scene, "b1").x()).toBeCloseTo(20, COORDS_DIGITS);
  });

  it("is dropped by Discard, and the box goes back as stored", async () => {
    const scene = await openOnCanvas();
    const grabbed = grab(scene, rectOf(scene, "b1"));
    grabbed.moveTo(10, 0);

    await scene.manager.discardChanges();
    grabbed.moveTo(20, 0);
    grabbed.release();

    expect(scene.manager.hasUnsavedWork).toBe(false);
    expect(scene.manager.pendingMutations).toEqual([]);
    expectCoords(scene.ctx.collection.find("b1")?.geometry, [0.1, 0.1, 0.2, 0.2]);
    const rect = rectOf(scene, "b1");
    expect([rect.x(), rect.y()]).toEqual([10, 10]);
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

describe("bboxEditor2D, a box on the image's edge resized past that edge", () => {
  // A box lying on an edge of the image — as a model's box of an object the
  // frame cuts often does — whose other handle is dragged past that same edge.
  // Without flips, Konva spans the box from the edge that stays to the pointer,
  // wholly outside the image, so the cut would leave nothing of it. It is kept
  // at the editor's least size instead, 1 px (0.01 of the 100 px image),
  // against the edge it lay on.
  const ON_THE_EDGE: [string, number[], Handle, number, number, number[]][] = [
    ["left", [0, 0.1, 0.2, 0.2], "middle-right", -40, 0, [0, 0.1, 0.01, 0.2]],
    ["right", [0.8, 0.1, 0.2, 0.2], "middle-left", 40, 0, [0.99, 0.1, 0.01, 0.2]],
    ["top", [0.1, 0, 0.2, 0.2], "bottom-center", 0, -40, [0.1, 0, 0.2, 0.01]],
    ["bottom", [0.1, 0.8, 0.2, 0.2], "top-center", 0, 40, [0.1, 0.99, 0.2, 0.01]],
  ];

  it.each(ON_THE_EDGE)(
    "%s edge: saves the box at the least size against it, and draws it there",
    async (_, stored, handle, dx, dy, expected) => {
      const scene = await openOnCanvas({ ...BOX, coords: stored });
      select(scene, "b1");

      resizeFrom(scene, handle, dx, dy);

      expectCoords(scene.ctx.collection.find("b1")?.geometry, expected);
      expectInsideTheImage(queuedCoords(scene), expected);
      scene.redraw();
      const drawn = rectOf(scene, "b1").getClientRect({ skipStroke: true });
      expectCoords(
        [drawn.x, drawn.y, drawn.width, drawn.height],
        expected.map((value) => value * IMAGE_PIXELS),
      );
    },
  );

  it("sends the server the box at the least size, once saved", async () => {
    const scene = await openOnCanvas({ ...humanBox(REC, "h1"), coords: [0, 0.1, 0.2, 0.2] });
    select(scene, "h1");

    resizeFrom(scene, "middle-right", -40, 0);
    await scene.manager.flushSave();

    expect(scene.manager.saveError).toBeNull();
    const sent = scene.backend.writes.find((w) => w.op === "update");
    expectInsideTheImage(sent?.op === "update" ? sent.body.coords : undefined, [0, 0.1, 0.01, 0.2]);
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

describe("bboxEditor2D, Delete pressed while a gesture runs", () => {
  // The key reaches the select tool while the mouse still holds the box: the
  // gesture is let go of first, so the delete applies to the box as stored, and
  // the release that follows commits nothing over it.

  /** Delete pressed on the canvas, as the image widget hands it to the select tool. */
  function pressDelete(scene: OnCanvas): void {
    expect(scene.selectTool.onKeyDown!(new KeyboardEvent("keydown", { key: "Delete" }))).toBe(true);
  }

  /** The bodies of the updates queued, in order. */
  const queuedBodies = (scene: OnCanvas) =>
    scene.manager.pendingMutations.map((m) => (m.op === "update" ? m.body : m.op));

  /** The gesture's flag: raised once as it began, lowered since. */
  function expectFlagLowered(scene: OnCanvas): void {
    expect(scene.flagSets.filter((staged) => staged)).toEqual([true]);
    expect(scene.flagSets.at(-1)).toBe(false);
  }

  it("deletes a person's box being resized, and Konva throws nothing after", async () => {
    const scene = await openOnCanvas(humanBox(REC, "h1"));
    select(scene, "h1");
    const grabbed = grabHandle(scene, "bottom-right");
    grabbed.moveTo(10, 10);

    pressDelete(scene);
    expect(() => grabbed.moveTo(20, 20)).not.toThrow();
    grabbed.release();

    expect(scene.manager.annotations.find("h1")).toBeUndefined();
    expect(queuedBodies(scene)).toEqual(["delete"]);
    expectFlagLowered(scene);
    expect(scene.manager.unsavedCount).toBe(1);
  });

  it("deletes a person's box being dragged, and nothing is left unsaved once saved", async () => {
    const scene = await openOnCanvas(humanBox(REC, "h1"));
    select(scene, "h1");
    const grabbed = grab(scene, rectOf(scene, "h1"));
    grabbed.moveTo(10, 0);

    pressDelete(scene);
    grabbed.moveTo(20, 0);
    grabbed.release();

    expect(scene.manager.annotations.find("h1")).toBeUndefined();
    expect(queuedBodies(scene)).toEqual(["delete"]);
    expectFlagLowered(scene);
    expect(scene.manager.unsavedCount).toBe(1);
    await scene.manager.flushSave();
    expect(scene.backend.writes.map((w) => w.op)).toEqual(["delete"]);
    expect(scene.manager.hasUnsavedWork).toBe(false);
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
