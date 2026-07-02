/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { describe, expect, it, vi } from "vitest";

import { AnnotationCollection, type LocalBBox } from "../../annotationCollection.svelte.js";
import { selectTool2D } from "../selectTool2D.js";
import type { Scene2DContext } from "../sceneContext.js";
import { DEFAULT_TOOL_2D } from "../tool.js";

function makeBBox(id: string, persisted = true): LocalBBox {
  return { id, entityId: `e-${id}`, kind: "bbox", viewId: "view", geometry: [0.1, 0.1, 0.2, 0.2], persisted };
}

function makeContext(collection: AnnotationCollection) {
  const stage = {} as Konva.Stage;
  const ctx: Scene2DContext = {
    widgetId: "w1",
    buildContext: { datasetId: "ds", recordId: "rec", viewId: "view" },
    collection,
    mutations: {
      pending: [],
      queue: vi.fn(),
      upsertUpdate: vi.fn(),
      patchPendingCreate: vi.fn(),
      dropForLocalAnnotation: vi.fn(),
    },
    stage,
    annotationLayer: {} as Konva.Layer,
    camera: { imageWidth: 100, imageHeight: 100, calibration: null },
    getKonvaImage: () => null,
    setActiveTool: vi.fn(),
    requestRedraw: vi.fn(),
  };
  return { ctx, stage };
}

describe("selectTool2D", () => {
  it("is the default tool", () => {
    expect(selectTool2D.id).toBe(DEFAULT_TOOL_2D);
  });

  it("deselects when clicking the empty stage", () => {
    const collection = new AnnotationCollection([makeBBox("a")]);
    collection.select("a");
    const { ctx, stage } = makeContext(collection);
    const handler = selectTool2D.createHandler(ctx);

    handler.onPointerDown!({ target: stage } as Parameters<NonNullable<typeof handler.onPointerDown>>[0]);

    expect(collection.selectedId).toBeNull();
    expect(ctx.requestRedraw).toHaveBeenCalled();
  });

  it("keeps the selection when clicking a shape", () => {
    const collection = new AnnotationCollection([makeBBox("a")]);
    collection.select("a");
    const { ctx } = makeContext(collection);
    const handler = selectTool2D.createHandler(ctx);

    handler.onPointerDown!({ target: { notTheStage: true } } as unknown as Parameters<
      NonNullable<typeof handler.onPointerDown>
    >[0]);

    expect(collection.selectedId).toBe("a");
  });

  it("Escape deselects", () => {
    const collection = new AnnotationCollection([makeBBox("a")]);
    collection.select("a");
    const { ctx } = makeContext(collection);
    const handler = selectTool2D.createHandler(ctx);

    expect(handler.onKeyDown!(new KeyboardEvent("keydown", { key: "Escape" }))).toBe(true);
    expect(collection.selectedId).toBeNull();
  });

  it("Delete queues backend deletes for a persisted selection and removes it", () => {
    const collection = new AnnotationCollection([makeBBox("a", true)]);
    collection.select("a");
    const { ctx } = makeContext(collection);
    const handler = selectTool2D.createHandler(ctx);

    expect(handler.onKeyDown!(new KeyboardEvent("keydown", { key: "Delete" }))).toBe(true);

    expect(collection.find("a")).toBeUndefined();
    // One delete for the bbox row, one for its parent entity.
    expect(ctx.mutations.queue).toHaveBeenCalledTimes(2);
    expect(ctx.mutations.queue).toHaveBeenCalledWith(
      expect.objectContaining({ op: "delete", resource: "bboxes", id: "a" }),
    );
    expect(ctx.mutations.queue).toHaveBeenCalledWith(
      expect.objectContaining({ op: "delete", resource: "entities", id: "e-a" }),
    );
  });

  it("Delete drops pending creates for an unsaved selection instead of queueing", () => {
    const collection = new AnnotationCollection([makeBBox("a", false)]);
    collection.select("a");
    const { ctx } = makeContext(collection);
    const handler = selectTool2D.createHandler(ctx);

    handler.onKeyDown!(new KeyboardEvent("keydown", { key: "Backspace" }));

    expect(collection.find("a")).toBeUndefined();
    expect(ctx.mutations.queue).not.toHaveBeenCalled();
    expect(ctx.mutations.dropForLocalAnnotation).toHaveBeenCalledWith("a");
  });

  it("ignores Delete without a selection and unrelated keys", () => {
    const collection = new AnnotationCollection([makeBBox("a")]);
    const { ctx } = makeContext(collection);
    const handler = selectTool2D.createHandler(ctx);

    expect(handler.onKeyDown!(new KeyboardEvent("keydown", { key: "Delete" }))).toBe(false);
    expect(handler.onKeyDown!(new KeyboardEvent("keydown", { key: "a" }))).toBe(false);
    expect(ctx.mutations.queue).not.toHaveBeenCalled();
  });
});
