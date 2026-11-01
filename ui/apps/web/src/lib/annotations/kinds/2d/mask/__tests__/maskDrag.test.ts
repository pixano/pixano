/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MASK_RESOURCE } from "../maskPayloadBuilder.js";
import { maskRenderer2DFactory } from "../maskRenderer2D.js";
import { MASK_DRAGGING_ATTR, MASK_ID_ATTR, type MaskGeometry } from "../maskTypes.js";
import { commitGeometryEdit } from "$lib/annotations/payloadBuilders.js";
import { installSilentCanvas } from "$lib/annotations/scene/__tests__/konvaInHappyDom.js";
import type { Scene2DContext, StagedWorkFlag } from "$lib/annotations/scene/sceneContext.js";
import { selectTool2D } from "$lib/annotations/scene/selectTool2D.js";
import { rleToString } from "$lib/utils/maskUtils.js";
import {
  openManager,
  viewIdOf,
  widgetSeam,
  type Row,
} from "$lib/workspace/__tests__/workspaceHarness.js";

// The editor and the renderer run on the real Konva, over the real workspace:
// whether a drag survives a save depends on where Konva leaves the dragged node
// and on what the renderer's sync does to it. Konva's browser build, as the app
// loads it (see konvaInHappyDom.ts).
vi.mock("konva", async () => ({
  default: (await vi.importActual<{ default: unknown }>("konva/lib/index.js")).default,
}));

// The test DOM has no OffscreenCanvas, which the raster round-trip draws on: a
// mask is drawn as a plain canvas the size of its grid, and its move is
// stubbed. What is under test is the drag — how far it went, and when it is
// read — not the re-encoding of the moved pixels.
const translateMask = vi.hoisted(() => vi.fn());
vi.mock("../maskRaster.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../maskRaster.js")>()),
  decodeMask: (geometry: MaskGeometry) => {
    const canvas = document.createElement("canvas");
    [canvas.height, canvas.width] = geometry.size;
    return canvas;
  },
  tintMask: (source: unknown) => source,
  translateMask,
}));

installSilentCanvas();

const REC = "rec-1";
/** The displayed image: 100 × 100 px at the stage origin. */
const IMAGE_PIXELS = 100;
const STAGE_PIXELS = 200;
/** The mask's own grid: 10 × 10, so one grid pixel is drawn 10 px wide. */
const GRID = 10;
const PIXELS_PER_CELL = IMAGE_PIXELS / GRID;
/** How many moves a pointer drag is made of: a mouse reports a drag in steps, not in one jump. */
const DRAG_STEPS = 8;

/** Column-major run lengths: the first column's top four cells painted. */
const STORED_COUNTS = rleToString([0, 4, GRID * GRID - 4]);
/** What the stubbed move hands back, whatever the move: the same cells, three columns on. */
const MOVED_COUNTS = rleToString([3 * GRID, 4, GRID * GRID - 3 * GRID - 4]);

/** A mask a person painted, on the first column's top four cells. */
function humanMask(id: string): Row {
  return {
    id,
    record_id: REC,
    entity_id: `ent-${id}`,
    view_id: viewIdOf(REC),
    size: [GRID, GRID],
    counts: STORED_COUNTS,
    source_type: "other",
    source_name: "Pixano",
    source_metadata: "{}",
  };
}

afterEach(() => {
  // Konva's drags are global: one a failed test left running would move with
  // the next test's pointer. Let go of it, so each test starts with none.
  window.dispatchEvent(new MouseEvent("mouseup"));
  document.body.innerHTML = "";
});

beforeEach(() => {
  translateMask.mockReset().mockImplementation((geometry: MaskGeometry) => ({
    size: geometry.size,
    counts: MOVED_COUNTS,
  }));
});

/**
 * The record open on a real stage, with the mask renderer and editor the image
 * widget wires: a person's mask `m1`, and `others` after it.
 */
async function openOnCanvas(...others: Row[]) {
  const opened = await openManager({ [REC]: { [MASK_RESOURCE]: [humanMask("m1"), ...others] } });
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
  const renderer = maskRenderer2DFactory.create(ctx);
  const editor = maskRenderer2DFactory.createEditor!(ctx);
  function redraw(): void {
    renderer.sync();
    editor.syncSelection();
  }
  redraw();
  // The tool the image widget hands its keys to.
  const selectTool = selectTool2D.createHandler(ctx);
  return { ...opened, ctx, stage, layer, renderer, editor, redraw, flagSets, selectTool };
}

type OnCanvas = Awaited<ReturnType<typeof openOnCanvas>>;

/** The node the renderer draws a mask with. */
function nodeOf(scene: OnCanvas, id: string): Konva.Image {
  const node = scene.layer.getChildren().find((child) => child.getAttr(MASK_ID_ATTR) === id);
  if (!node) throw new Error(`no node for ${id}`);
  return node as Konva.Image;
}

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

/** The grid cells the mask was moved by, as the editor read them off the drag. */
function cellsMoved(): [number, number] {
  expect(translateMask).toHaveBeenCalledTimes(1);
  const [geometry, dx, dy] = translateMask.mock.calls[0] as [MaskGeometry, number, number];
  expect(geometry.counts).toBe(STORED_COUNTS);
  return [Math.round(dx), Math.round(dy)];
}

function queuedCounts(scene: OnCanvas): unknown {
  const update = scene.manager.pendingMutations.find((m) => m.op === "update");
  return update?.op === "update" ? update.body.counts : undefined;
}

/**
 * A person's edit of mask `m2`, queued as an editor commits a gesture's end:
 * something for the next save to send.
 */
function editOtherMask(scene: OnCanvas): void {
  commitGeometryEdit(scene.ctx, "m2", { size: [GRID, GRID], counts: MOVED_COUNTS });
}

describe("maskEditor2D on the real Konva, a drag still running when a save ends", () => {
  it("holds the mask as unsaved work from dragstart to dragend, raising the flag once", async () => {
    const scene = await openOnCanvas();
    const grabbed = grab(scene, nodeOf(scene, "m1"));

    grabbed.moveTo(10, 0);
    grabbed.moveTo(3 * PIXELS_PER_CELL, 0);

    // Raised as the drag began, not again at each of the pointer's moves.
    expect(scene.flagSets).toEqual([true]);
    expect(scene.manager.hasUnsavedWork).toBe(true);
    expect(nodeOf(scene, "m1").getAttr(MASK_DRAGGING_ATTR)).toBe(true);
    grabbed.release();

    expect(scene.flagSets).toEqual([true, false]);
    expect(cellsMoved()).toEqual([3, 0]);
    expect(queuedCounts(scene)).toBe(MOVED_COUNTS);
    // Placed back on the image, the move baked into the mask.
    const node = nodeOf(scene, "m1");
    expect(node.getAttr(MASK_DRAGGING_ATTR)).toBe(false);
    expect([node.x(), node.y()]).toEqual([0, 0]);
  });

  it("is not put back by the save: it is saved once let go", async () => {
    const scene = await openOnCanvas(humanMask("m2"));
    // Something for the save to send.
    editOtherMask(scene);
    const grabbed = grab(scene, nodeOf(scene, "m1"));
    grabbed.moveTo(PIXELS_PER_CELL, 0);

    expect(await scene.manager.flushSave()).toBe(false);
    // A save ends by clearing the selection, and the widget syncs its scene then.
    scene.redraw();
    expect(nodeOf(scene, "m1").x()).toBe(PIXELS_PER_CELL);
    grabbed.moveTo(3 * PIXELS_PER_CELL, 0);
    grabbed.release();

    expect(cellsMoved()).toEqual([3, 0]);
    expect(queuedCounts(scene)).toBe(MOVED_COUNTS);
  });

  it("is saved where it stood when let go right as the save ends", async () => {
    const scene = await openOnCanvas(humanMask("m2"));
    editOtherMask(scene);
    const grabbed = grab(scene, nodeOf(scene, "m1"));
    grabbed.moveTo(2 * PIXELS_PER_CELL, 0);

    await scene.manager.flushSave();
    scene.redraw();
    // Let go where it was: no later move puts the mask back where it was dragged.
    grabbed.release();

    expect(cellsMoved()).toEqual([2, 0]);
    expect(queuedCounts(scene)).toBe(MOVED_COUNTS);
  });

  it("is dropped by Discard, and the mask goes back on the image as stored", async () => {
    const scene = await openOnCanvas();
    const grabbed = grab(scene, nodeOf(scene, "m1"));
    grabbed.moveTo(PIXELS_PER_CELL, 0);

    await scene.manager.discardChanges();
    grabbed.moveTo(3 * PIXELS_PER_CELL, 0);
    grabbed.release();

    expect(scene.manager.hasUnsavedWork).toBe(false);
    expect(scene.manager.pendingMutations).toEqual([]);
    expect(translateMask).not.toHaveBeenCalled();
    const node = nodeOf(scene, "m1");
    expect([node.x(), node.y()]).toEqual([0, 0]);
  });

  it("neither holds nor commits the drag of a node that is no mask", async () => {
    const scene = await openOnCanvas();
    const other = new Konva.Rect({ width: 5, height: 5, name: "other", draggable: true });
    scene.layer.add(other);
    const grabbed = grab(scene, other);

    grabbed.moveTo(10, 10);
    grabbed.release();

    expect(scene.flagSets).toEqual([]);
    expect(scene.manager.hasUnsavedWork).toBe(false);
  });

  it("lowers the flag when the editor goes mid-drag, the widget closing", async () => {
    const scene = await openOnCanvas();
    const grabbed = grab(scene, nodeOf(scene, "m1"));
    grabbed.moveTo(PIXELS_PER_CELL, 0);

    scene.editor.destroy();

    expect(scene.flagSets).toEqual([true, false]);
    expect(nodeOf(scene, "m1").getAttr(MASK_DRAGGING_ATTR)).toBe(false);
    grabbed.release();
    expect(scene.manager.pendingMutations).toEqual([]);
  });
});

describe("maskEditor2D on the real Konva, Delete pressed while a drag runs", () => {
  it("deletes a person's mask being dragged: the half-done move is dropped", async () => {
    const scene = await openOnCanvas();
    scene.ctx.collection.select("m1");
    scene.redraw();
    const grabbed = grab(scene, nodeOf(scene, "m1"));
    grabbed.moveTo(3 * PIXELS_PER_CELL, 0);

    expect(scene.selectTool.onKeyDown!(new KeyboardEvent("keydown", { key: "Delete" }))).toBe(true);
    grabbed.moveTo(5 * PIXELS_PER_CELL, 0);
    grabbed.release();

    expect(scene.manager.annotations.find("m1")).toBeUndefined();
    expect(translateMask).not.toHaveBeenCalled();
    expect(scene.manager.pendingMutations.map((m) => m.op)).toEqual(["delete"]);
    expect(scene.flagSets.at(-1)).toBe(false);
    expect(scene.manager.unsavedCount).toBe(1);
  });
});
