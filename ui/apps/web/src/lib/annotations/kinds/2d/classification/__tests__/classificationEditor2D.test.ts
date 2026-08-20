/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createClassificationEditor2D } from "../classificationEditor2D.js";
import { CLASSIFICATION_ID_ATTR, CLASSIFICATION_NODE_NAME } from "../classificationTypes.js";
import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import type { PendingAnnotation } from "$lib/annotations/types.js";

const EVENT = "dblclick.classification-edit dbltap.classification-edit";

/** The chip group as the renderer stamps it. */
function fakeChip(id = "a1") {
  return {
    name: () => CLASSIFICATION_NODE_NAME,
    getAttr: (k: string) => (k === CLASSIFICATION_ID_ATTR ? id : undefined),
    getParent: () => null,
  };
}

/** A Konva.Text inside the chip — what a double-click actually lands on. */
function fakeChipChild(id = "a1") {
  return { name: () => "", getAttr: () => undefined, getParent: () => fakeChip(id) };
}

function makeHarness() {
  const collection = new AnnotationCollection();
  const handlers: Record<string, (e: { target: unknown }) => void> = {};
  const upsertUpdate = vi.fn();
  const queue = vi.fn();
  const off = vi.fn();
  let pending: PendingAnnotation | null = null;
  const ctx = {
    widgetId: "w1",
    buildContext: { datasetId: "ds", recordId: "rec", viewId: "view-1" },
    collection,
    mutations: {
      pending: [],
      queue,
      upsertUpdate,
      patchPendingCreate: vi.fn(),
      dropForLocalAnnotation: vi.fn(),
    },
    annotationLayer: {
      on: (evt: string, fn: (e: { target: unknown }) => void) => (handlers[evt] = fn),
      off,
    } as unknown as Konva.Layer,
    beginPendingAnnotation: (p: PendingAnnotation) => (pending = p),
    findEntity: (entityId: string) => ({ id: entityId, name: "existing-class" }),
    requestRedraw: vi.fn(),
  } as unknown as Scene2DContext;
  return { ctx, collection, handlers, upsertUpdate, queue, off, getPending: () => pending };
}

describe("classificationEditor2D", () => {
  let harness: ReturnType<typeof makeHarness>;
  const dblclick = (target: unknown) => harness.handlers[EVENT]({ target });

  beforeEach(() => {
    harness = makeHarness();
    createClassificationEditor2D(harness.ctx);
    harness.collection.add({
      id: "a1",
      entityId: "e1",
      kind: "classification",
      viewId: "view-1",
      geometry: { labels: ["cat"], confidences: [1] },
      persisted: true,
    });
  });

  it("relabels from a newly typed class and queues its entity", () => {
    dblclick(fakeChip());
    harness.getPending()?.onConfirm({ mode: "new", entityFields: { name: "dog" } });

    expect(harness.collection.find("a1")?.geometry).toEqual({
      labels: ["dog"],
      confidences: [1],
    });
    // One entity create for the new class, one update carrying the new labels.
    expect(harness.queue).toHaveBeenCalledTimes(1);
    expect(harness.upsertUpdate).toHaveBeenCalledTimes(1);
  });

  it("relabels from an existing entity's label", () => {
    dblclick(fakeChip());
    harness.getPending()?.onConfirm({ mode: "existing", entityId: "e9" });

    expect(harness.collection.find("a1")?.geometry).toMatchObject({ labels: ["existing-class"] });
    expect(harness.collection.find("a1")?.entityId).toBe("e9");
  });

  it("opens from a double-click on a chip's child node", () => {
    dblclick(fakeChipChild());

    expect(harness.getPending()).not.toBeNull();
  });

  it("keeps the old class when the choice yields an empty label", () => {
    dblclick(fakeChip());
    harness.getPending()?.onConfirm({ mode: "new", entityFields: { name: "   " } });

    expect(harness.collection.find("a1")?.geometry).toMatchObject({ labels: ["cat"] });
    expect(harness.upsertUpdate).not.toHaveBeenCalled();
  });

  it("leaves the classification untouched when the form is cancelled", () => {
    dblclick(fakeChip());
    harness.getPending()?.onCancel?.();

    expect(harness.collection.find("a1")?.geometry).toMatchObject({ labels: ["cat"] });
    expect(harness.upsertUpdate).not.toHaveBeenCalled();
  });

  it("ignores a double-click outside any chip", () => {
    dblclick({ name: () => "pixano-bbox", getAttr: () => undefined, getParent: () => null });

    expect(harness.getPending()).toBeNull();
  });

  it("stops listening once destroyed", () => {
    createClassificationEditor2D(harness.ctx).destroy();

    expect(harness.off).toHaveBeenCalledWith(EVENT);
  });
});
