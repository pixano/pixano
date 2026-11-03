/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MASK_RESOURCE } from "../maskPayloadBuilder.js";
import { maskBounds } from "../maskRaster.js";
import { maskRenderer2DFactory } from "../maskRenderer2D.js";
import { MASK_ID_ATTR, type MaskGeometry } from "../maskTypes.js";
import { IMAGE_SIZE, TRIANGLE, TRIANGLE_MOVED, TRIANGLE_SHIFT } from "./pycocotoolsMasks.js";
import { REVIEW_STATUS } from "$lib/annotations/reviewStatus.js";
import { installSilentCanvas } from "$lib/annotations/scene/__tests__/konvaInHappyDom.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import { rleFrString } from "$lib/utils/maskUtils.js";
import {
  entityOf,
  modelMask,
  openManager,
  serveLikeTheApi,
  widgetSeam,
  type Row,
} from "$lib/workspace/__tests__/workspaceHarness.js";

// A mask a segmentation job wrote, moved by a person the way the image widget
// lets them: pressed and dragged on the real Konva, over the real workspace —
// renderer, editor, the raster round trip, the queue and the save.
// `maskDrag.test.ts` pins when a drag is read; this file pins what it writes:
// the moved mask, as pycocotools would encode it, stored accepted.
// Konva's browser build, as the app loads it (see konvaInHappyDom.ts).
vi.mock("konva", async () => ({
  default: (await vi.importActual<{ default: unknown }>("konva/lib/index.js")).default,
}));

installSilentCanvas();

/** Red, green, blue and alpha: the channels of one pixel of image data. */
const CHANNELS_PER_PIXEL = 4;
/** Where alpha sits among them: what tells a painted pixel of a mask from the background. */
const ALPHA_CHANNEL = 3;

class FakeImageData {
  readonly data: Uint8ClampedArray;
  constructor(
    readonly width: number,
    readonly height: number,
  ) {
    this.data = new Uint8ClampedArray(width * height * CHANNELS_PER_PIXEL);
  }
}

/**
 * The test DOM has no `OffscreenCanvas`, which the raster round trip draws on.
 * This one holds real pixels and does what `maskRaster.ts` asks of a canvas:
 * image data in and out, and `drawImage` at an offset, clipped to the canvas —
 * the move itself. The tint's fill is not drawn: the colour is display, and
 * the mask's footprint, all a move reads back, is left as it was.
 */
class FakeOffscreenCanvas {
  pixels: FakeImageData;
  constructor(
    readonly width: number,
    readonly height: number,
  ) {
    this.pixels = new FakeImageData(width, height);
  }

  getContext() {
    return {
      globalCompositeOperation: "source-over",
      globalAlpha: 1,
      fillStyle: "",
      createImageData: (width: number, height: number) => new FakeImageData(width, height),
      putImageData: (data: FakeImageData) => {
        this.pixels = data;
      },
      getImageData: () => this.pixels,
      drawImage: (source: FakeOffscreenCanvas, dx: number, dy: number) =>
        this.drawAt(source, dx, dy),
      fillRect: () => undefined,
    };
  }

  /** Copy the source's painted pixels `dx`, `dy` further on; what falls outside is lost. */
  private drawAt(source: FakeOffscreenCanvas, dx: number, dy: number): void {
    for (let y = 0; y < source.height; y++) {
      for (let x = 0; x < source.width; x++) {
        const from = (y * source.width + x) * CHANNELS_PER_PIXEL;
        if (source.pixels.data[from + ALPHA_CHANNEL] === 0) continue;
        const [toX, toY] = [x + dx, y + dy];
        if (toX < 0 || toY < 0 || toX >= this.width || toY >= this.height) continue;
        const to = (toY * this.width + toX) * CHANNELS_PER_PIXEL;
        this.pixels.data.set(source.pixels.data.subarray(from, from + CHANNELS_PER_PIXEL), to);
      }
    }
  }
}

const REC = "rec-1";
const MASK_ID = "m1";
const ENTITY_ID = `ent-${MASK_ID}`;
/** What the worker writes as a segmentation job's provenance (pixano_worker.writer.provenance). */
const SEGMENTATION_METADATA = JSON.stringify({
  job_id: "job-2",
  kind: "segmentation",
  model: "sam2.1-hiera-tiny",
});

/** Stage pixels one grid pixel of the image is drawn on: the image is shown 5× its size. */
const DISPLAY_SCALE = 5;
/** Where the image sits on the stage: not at its origin, as when the widget centres it. */
const FRAME_X = 30;
const FRAME_Y = 20;
const STAGE_WIDTH = 300;
const STAGE_HEIGHT = 200;
/** How many moves a pointer drag is made of: a mouse reports a drag in steps, not in one jump. */
const DRAG_STEPS = 8;

afterEach(() => {
  // Konva's drags are global: one a failed test left running would move with
  // the next test's pointer. Let go of it, so each test starts with none.
  window.dispatchEvent(new MouseEvent("mouseup"));
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
});

beforeEach(() => {
  vi.stubGlobal("OffscreenCanvas", FakeOffscreenCanvas);
});

/** The mask the job wrote on its non-square image, pending review. */
function jobMask(): Row {
  return {
    ...modelMask(REC, MASK_ID),
    size: [...TRIANGLE.size],
    counts: TRIANGLE.counts,
    source_metadata: SEGMENTATION_METADATA,
  };
}

/** The record open on a real stage, with the mask renderer and editor the image widget wires. */
async function openOnCanvas() {
  const opened = await openManager(
    { [REC]: { [MASK_RESOURCE]: [jobMask()] } },
    { entities: [entityOf(REC, ENTITY_ID, { name: "triangle" })] },
  );
  serveLikeTheApi(opened.backend, REC);
  const container = document.createElement("div");
  document.body.appendChild(container);
  const stage = new Konva.Stage({ container, width: STAGE_WIDTH, height: STAGE_HEIGHT });
  const layer = new Konva.Layer();
  stage.add(layer);
  const [gridHeight, gridWidth] = IMAGE_SIZE;
  const image = new Konva.Image({
    image: undefined,
    x: FRAME_X,
    y: FRAME_Y,
    width: gridWidth * DISPLAY_SCALE,
    height: gridHeight * DISPLAY_SCALE,
  });
  layer.add(image);
  const ctx: Scene2DContext = {
    ...widgetSeam(opened.manager),
    stage,
    annotationLayer: layer,
    getKonvaImage: () => image,
    camera: { imageWidth: gridWidth, imageHeight: gridHeight, calibration: null },
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
  return { ...opened, stage, layer };
}

type OnCanvas = Awaited<ReturnType<typeof openOnCanvas>>;

/** The node the renderer draws the mask with. */
function maskNode(scene: OnCanvas): Konva.Image {
  const node = scene.layer.getChildren().find((child) => child.getAttr(MASK_ID_ATTR) === MASK_ID);
  if (!node) throw new Error(`no node for ${MASK_ID}`);
  return node as Konva.Image;
}

/** Press the mouse on a node, take the pointer (dx, dy) px further in steps, and let go there. */
function drag(scene: OnCanvas, node: Konva.Node, dx: number, dy: number): void {
  const from = node.getAbsolutePosition();
  const down = new MouseEvent("mousedown", { clientX: from.x, clientY: from.y, bubbles: true });
  scene.stage.setPointersPositions(down);
  node.fire("mousedown", { evt: down, target: node });
  for (let step = 1; step <= DRAG_STEPS; step++) {
    window.dispatchEvent(
      new MouseEvent("mousemove", {
        clientX: from.x + (dx * step) / DRAG_STEPS,
        clientY: from.y + (dy * step) / DRAG_STEPS,
      }),
    );
  }
  window.dispatchEvent(new MouseEvent("mouseup", { clientX: from.x + dx, clientY: from.y + dy }));
}

/** Where the paint is in the mask's grid. */
function paintOf(geometry: MaskGeometry) {
  return maskBounds(rleFrString(geometry.counts), geometry.size);
}

describe("a segmentation job's mask moved on the real Konva", () => {
  it("is saved as the person's edit, accepted, moved by the grid pixels it was dragged", async () => {
    const scene = await openOnCanvas();
    const node = maskNode(scene);
    // Laid over the image: at its place on the stage, scaled from grid to screen.
    expect([node.x(), node.y(), node.scaleX(), node.scaleY()]).toEqual([
      FRAME_X,
      FRAME_Y,
      DISPLAY_SCALE,
      DISPLAY_SCALE,
    ]);

    drag(scene, node, TRIANGLE_SHIFT.columns * DISPLAY_SCALE, TRIANGLE_SHIFT.rows * DISPLAY_SCALE);

    // Queued as one update of the mask, the move baked into its pixels: what
    // pycocotools encodes for the same mask moved as far.
    expect(scene.manager.pendingMutations).toHaveLength(1);
    const [queued] = scene.manager.pendingMutations;
    expect(queued).toMatchObject({ op: "update", resource: MASK_RESOURCE, id: MASK_ID });
    expect(queued.op === "update" && queued.body).toMatchObject({
      entity_id: ENTITY_ID,
      size: IMAGE_SIZE,
      counts: TRIANGLE_MOVED.counts,
    });
    // Unsaved, the move leaves the mask in review.
    expect(scene.manager.annotations.find(MASK_ID)?.review?.status).toBe(REVIEW_STATUS.PENDING);

    expect(await scene.manager.flushSave()).toBe(true);

    // Stored accepted, the model's provenance kept: the person's move of the
    // job's mask, not a mask of the person's own.
    expect(scene.backend.writes.map((write) => `${write.op} ${write.resource}`)).toEqual([
      `update ${MASK_RESOURCE}`,
    ]);
    expect(scene.backend.records[REC][MASK_RESOURCE]).toEqual([
      expect.objectContaining({
        id: MASK_ID,
        entity_id: ENTITY_ID,
        size: IMAGE_SIZE,
        counts: TRIANGLE_MOVED.counts,
        review_status: REVIEW_STATUS.ACCEPTED,
        source_type: "model",
        source_name: "segmentation",
        source_metadata: SEGMENTATION_METADATA,
      }),
    ]);
    // Shown as stored, and drawn there: the paint `TRIANGLE_SHIFT` further
    // right and down, the node back on the image's frame.
    const saved = scene.manager.annotations.find(MASK_ID);
    expect(saved?.review?.status).toBe(REVIEW_STATUS.ACCEPTED);
    expect(paintOf(saved?.geometry as MaskGeometry)).toEqual(TRIANGLE_MOVED.bounds);
    expect([maskNode(scene).x(), maskNode(scene).y()]).toEqual([FRAME_X, FRAME_Y]);
  });
});
