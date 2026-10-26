/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KEYPOINTS_RESOURCE } from "../keypointsPayloadBuilder.js";
import { keypointsRenderer2DFactory } from "../keypointsRenderer2D.js";
import {
  KEYPOINTS_DRAGGING_ATTR,
  KEYPOINTS_ID_ATTR,
  KEYPOINTS_VERTEX_INDEX_ATTR,
  KEYPOINTS_VERTEX_NAME,
} from "../keypointsTypes.js";
import { commitGeometryEdit } from "$lib/annotations/payloadBuilders.js";
import { installSilentCanvas } from "$lib/annotations/scene/__tests__/konvaInHappyDom.js";
import type { Scene2DContext, StagedWorkFlag } from "$lib/annotations/scene/sceneContext.js";
import { selectTool2D } from "$lib/annotations/scene/selectTool2D.js";
import {
  openManager,
  viewIdOf,
  widgetSeam,
  type Row,
} from "$lib/workspace/__tests__/workspaceHarness.js";

// The editor runs on the real Konva, over the real workspace: whether a drag
// survives a save depends on which nodes Konva keeps dragging, and on what it
// fires as a dragged node is rebuilt — which a mocked Konva would only say what
// the mock says. Konva's browser build, as the app loads it (konvaInHappyDom.ts).
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
/** How many moves a pointer drag is made of: a mouse reports a drag in steps, not in one jump. */
const DRAG_STEPS = 8;

/**
 * A face: its eyes drawn at (10, 10) and (30, 10) px, its nose at (20, 20) and
 * its mouth at (20, 30), joined by the template's bones.
 */
const FACE = [0.1, 0.1, 0.3, 0.1, 0.2, 0.2, 0.2, 0.3];
/** The face moved 10 px right, whole. */
const FACE_MOVED_10 = [0.2, 0.1, 0.4, 0.1, 0.3, 0.2, 0.3, 0.3];
const FACE_STATES = ["visible", "visible", "visible", "visible"];

/** A skeleton a person placed: the face. */
function humanSkeleton(id: string): Row {
  return {
    id,
    record_id: REC,
    entity_id: `ent-${id}`,
    view_id: viewIdOf(REC),
    template_id: "face",
    coords: FACE,
    states: FACE_STATES,
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

/**
 * The record open on a real stage, with the keypoints renderer and editor the
 * image widget wires: a person's skeleton `k1`, and `others` after it.
 */
async function openOnCanvas(...others: Row[]) {
  const opened = await openManager({
    [REC]: { [KEYPOINTS_RESOURCE]: [humanSkeleton("k1"), ...others] },
  });
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
  const renderer = keypointsRenderer2DFactory.create(ctx);
  const editor = keypointsRenderer2DFactory.createEditor!(ctx);
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

/** The group the renderer draws a skeleton with. */
function groupOf(scene: OnCanvas, id: string): Konva.Group {
  const group = scene.layer.getChildren().find((node) => node.getAttr(KEYPOINTS_ID_ATTR) === id);
  if (!group) throw new Error(`no group for ${id}`);
  return group as Konva.Group;
}

/** The circle of one point of a skeleton — a handle once the skeleton is selected. */
function vertexOf(scene: OnCanvas, id: string, index: number): Konva.Circle {
  const vertex = groupOf(scene, id)
    .find<Konva.Circle>(`.${KEYPOINTS_VERTEX_NAME}`)
    .find((node) => node.getAttr(KEYPOINTS_VERTEX_INDEX_ATTR) === index);
  if (!vertex) throw new Error(`no point ${index} on ${id}`);
  return vertex;
}

/** Select a skeleton as a click does, so its points can be dragged. */
function select(scene: OnCanvas, id: string): void {
  scene.ctx.collection.select(id);
  scene.redraw();
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

function expectCoords(actual: unknown, expected: number[]): void {
  expect(actual).toHaveLength(expected.length);
  (actual as number[]).forEach((value, index) =>
    expect(value).toBeCloseTo(expected[index], COORDS_DIGITS),
  );
}

function coordsOf(scene: OnCanvas, id: string): unknown {
  return (scene.ctx.collection.find(id)?.geometry as { coords?: number[] } | undefined)?.coords;
}

function queuedCoords(scene: OnCanvas): unknown {
  const update = scene.manager.pendingMutations.find((m) => m.op === "update");
  return update?.op === "update" ? update.body.coords : undefined;
}

/**
 * A person's edit of skeleton `k2`, queued as an editor commits a gesture's
 * end: something for the next save to send.
 */
function editOtherSkeleton(scene: OnCanvas): void {
  commitGeometryEdit(scene.ctx, "k2", {
    templateId: "face",
    coords: FACE_MOVED_10,
    states: FACE_STATES,
  });
}

/** Where the skeleton's points are drawn, in stage pixels and in point order. */
function drawnPoints(scene: OnCanvas, id: string): number[] {
  const group = groupOf(scene, id);
  return group
    .find<Konva.Circle>(`.${KEYPOINTS_VERTEX_NAME}`)
    .sort((a, b) => a.getAttr(KEYPOINTS_VERTEX_INDEX_ATTR) - b.getAttr(KEYPOINTS_VERTEX_INDEX_ATTR))
    .flatMap((vertex) => [vertex.x() + group.x(), vertex.y() + group.y()]);
}

describe("keypoints on the shared flatCoordsEditor2D, a drag still running when a save ends", () => {
  it("holds the skeleton as unsaved work from dragstart to dragend, raising the flag once", async () => {
    const scene = await openOnCanvas();
    const grabbed = grab(scene, groupOf(scene, "k1"));

    grabbed.moveTo(5, 0);
    grabbed.moveTo(10, 0);

    // Raised as the drag began, not again at each of the pointer's moves.
    expect(scene.flagSets).toEqual([true]);
    expect(scene.manager.hasUnsavedWork).toBe(true);
    expect(groupOf(scene, "k1").getAttr(KEYPOINTS_DRAGGING_ATTR)).toBe(true);
    grabbed.release();

    expect(scene.flagSets).toEqual([true, false]);
    expectCoords(coordsOf(scene, "k1"), FACE_MOVED_10);
    expectCoords(queuedCoords(scene), FACE_MOVED_10);
    // Rebuilt where the move put it, and no longer held.
    expect(groupOf(scene, "k1").getAttr(KEYPOINTS_DRAGGING_ATTR)).toBeFalsy();
    expectCoords(
      drawnPoints(scene, "k1"),
      FACE_MOVED_10.map((value) => value * IMAGE_PIXELS),
    );
  });

  it("a point is not cut short by the save: it is saved once let go", async () => {
    const scene = await openOnCanvas(humanSkeleton("k2"));
    // Something for the save to send.
    editOtherSkeleton(scene);
    select(scene, "k1");
    const grabbed = grab(scene, vertexOf(scene, "k1", 0));
    grabbed.moveTo(10, 0);

    expect(await scene.manager.flushSave()).toBe(false);
    // A save ends by clearing the selection, and the widget syncs its scene then.
    scene.redraw();
    grabbed.moveTo(20, 0);
    grabbed.release();

    // The first point moved 20 px right; the others stay.
    const expected = [0.3, 0.1, 0.3, 0.1, 0.2, 0.2, 0.2, 0.3];
    expectCoords(coordsOf(scene, "k1"), expected);
    expectCoords(queuedCoords(scene), expected);
  });

  it("a skeleton dragged whole and let go right as the save ends is saved where it stood", async () => {
    const scene = await openOnCanvas(humanSkeleton("k2"));
    editOtherSkeleton(scene);
    const grabbed = grab(scene, groupOf(scene, "k1"));
    grabbed.moveTo(10, 0);

    expect(await scene.manager.flushSave()).toBe(false);
    scene.redraw();
    // Let go where it was: no later move puts the skeleton back where it was dragged.
    grabbed.release();

    expectCoords(coordsOf(scene, "k1"), FACE_MOVED_10);
    expectCoords(queuedCoords(scene), FACE_MOVED_10);
  });

  it.each([
    ["a point", (scene: OnCanvas) => vertexOf(scene, "k1", 0)],
    ["the whole skeleton", (scene: OnCanvas) => groupOf(scene, "k1")],
  ])(
    "dragging %s is dropped by Discard: nothing is saved, and the skeleton is drawn as stored",
    async (_, nodeOf) => {
      const scene = await openOnCanvas();
      select(scene, "k1");
      const grabbed = grab(scene, nodeOf(scene));
      grabbed.moveTo(10, 0);

      await scene.manager.discardChanges();
      grabbed.moveTo(20, 0);
      grabbed.release();

      expect(scene.manager.hasUnsavedWork).toBe(false);
      expect(scene.manager.pendingMutations).toEqual([]);
      expectCoords(coordsOf(scene, "k1"), FACE);
      expectCoords(
        drawnPoints(scene, "k1"),
        FACE.map((value) => value * IMAGE_PIXELS),
      );
    },
  );

  it("neither holds nor commits the drag of a node that is no skeleton", async () => {
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
    const grabbed = grab(scene, groupOf(scene, "k1"));
    grabbed.moveTo(10, 0);

    scene.editor.destroy();

    expect(scene.flagSets).toEqual([true, false]);
    expect(groupOf(scene, "k1").getAttr(KEYPOINTS_DRAGGING_ATTR)).toBe(false);
    grabbed.release();
    expect(scene.manager.pendingMutations).toEqual([]);
  });
});

describe("keypoints on the shared flatCoordsEditor2D, Backspace pressed while a drag runs", () => {
  it.each([
    ["a point", (scene: OnCanvas) => vertexOf(scene, "k1", 0)],
    ["the whole skeleton", (scene: OnCanvas) => groupOf(scene, "k1")],
  ])(
    "dragging %s of a person's skeleton: deleted as stored, and nothing left unsaved once saved",
    async (_, nodeOf) => {
      const scene = await openOnCanvas();
      select(scene, "k1");
      const grabbed = grab(scene, nodeOf(scene));
      grabbed.moveTo(10, 0);

      expect(scene.selectTool.onKeyDown!(new KeyboardEvent("keydown", { key: "Backspace" }))).toBe(
        true,
      );
      grabbed.moveTo(20, 0);
      grabbed.release();

      expect(scene.manager.annotations.find("k1")).toBeUndefined();
      expect(scene.flagSets.at(-1)).toBe(false);
      await scene.manager.flushSave();
      // The delete alone reached the server, and the record is all saved.
      expect(scene.backend.writes.map((w) => w.op)).toEqual(["delete"]);
      expect(scene.manager.hasUnsavedWork).toBe(false);
    },
  );
});
