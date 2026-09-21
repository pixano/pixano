/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  AnnotationCollection,
  type LocalAnnotation,
} from "$lib/annotations/annotationCollection.svelte.js";
import {
  beginEntityReassign,
  type EntityReassignContext,
} from "$lib/annotations/payloadBuilders.js";
import type { PendingAnnotation } from "$lib/annotations/types.js";

function makeHarness() {
  const collection = new AnnotationCollection();
  const queue = vi.fn();
  const upsertUpdate = vi.fn();
  const dropPendingEntityCreate = vi.fn();
  const requestRedraw = vi.fn();
  let pending: PendingAnnotation | null = null;
  const ctx = {
    collection,
    mutations: { queue, upsertUpdate, dropPendingEntityCreate },
    buildContext: { datasetId: "ds", recordId: "rec", viewId: "v1" },
    widgetId: "w1",
    findEntity: (entityId: string) => ({ id: entityId, name: "picked" }),
    requestRedraw,
    beginPendingAnnotation: (p: PendingAnnotation) => (pending = p),
  } as unknown as EntityReassignContext;
  return {
    ctx,
    collection,
    queue,
    upsertUpdate,
    dropPendingEntityCreate,
    requestRedraw,
    getPending: () => pending,
  };
}

function seed(collection: AnnotationCollection, persisted: boolean): LocalAnnotation {
  const annotation: LocalAnnotation = {
    id: "a1",
    entityId: "old-entity",
    kind: "bbox",
    viewId: "v1",
    geometry: [0, 0, 0.1, 0.1],
    persisted,
  };
  collection.add(annotation);
  return annotation;
}

describe("beginEntityReassign", () => {
  let harness: ReturnType<typeof makeHarness>;

  beforeEach(() => {
    harness = makeHarness();
  });

  it("moves a saved annotation onto an existing entity", () => {
    const annotation = seed(harness.collection, true);

    beginEntityReassign(annotation, harness.ctx, { label: "annotation entity" });
    harness.getPending()?.onConfirm({ mode: "existing", entityId: "new-entity" });

    expect(harness.collection.find("a1")?.entityId).toBe("new-entity");
    expect(harness.upsertUpdate).toHaveBeenCalledTimes(1);
  });

  it("creates the entity first when the user types a new one", () => {
    const annotation = seed(harness.collection, true);

    beginEntityReassign(annotation, harness.ctx, { label: "annotation entity" });
    harness.getPending()?.onConfirm({ mode: "new", entityFields: { name: "tree" } });

    // One create for the entity, one update pointing the annotation at it.
    expect(harness.queue).toHaveBeenCalledTimes(1);
    expect(harness.upsertUpdate).toHaveBeenCalledTimes(1);
  });

  it("refuses a draft, whose entity the create flow is still choosing", () => {
    const annotation = seed(harness.collection, false);

    beginEntityReassign(annotation, harness.ctx, { label: "annotation entity" });

    // Opening a second picker alongside the create flow would queue two
    // entities for one shape.
    expect(harness.getPending()).toBeNull();
    expect(harness.upsertUpdate).not.toHaveBeenCalled();
  });

  it("abandons the entity a superseded choice was going to create", () => {
    const annotation = seed(harness.collection, true);

    beginEntityReassign(annotation, harness.ctx, { label: "l" });
    harness.getPending()?.onConfirm({ mode: "new", entityFields: { name: "first-guess" } });
    beginEntityReassign(annotation, harness.ctx, { label: "l" });
    harness.getPending()?.onConfirm({ mode: "new", entityFields: { name: "corrected" } });

    // Correcting a mistake before saving must not litter: `upsertUpdate` leaves
    // only the last choice referenced, so without this the first entity was
    // written to the dataset with nothing pointing at it.
    expect(harness.dropPendingEntityCreate).toHaveBeenCalledWith("a1");
  });

  it("abandons a typed entity even when the correction lands on an existing one", () => {
    const annotation = seed(harness.collection, true);

    beginEntityReassign(annotation, harness.ctx, { label: "l" });
    harness.getPending()?.onConfirm({ mode: "new", entityFields: { name: "typo" } });
    harness.dropPendingEntityCreate.mockClear();
    beginEntityReassign(annotation, harness.ctx, { label: "l" });
    harness.getPending()?.onConfirm({ mode: "existing", entityId: "real-entity" });

    // Picking from the list abandons a name typed a moment earlier just as
    // surely as typing another one does; guarding only the new→new case left
    // this orphan in the dataset.
    expect(harness.dropPendingEntityCreate).toHaveBeenCalledWith("a1");
    expect(harness.collection.find("a1")?.entityId).toBe("real-entity");
  });

  it("leaves everything alone when the form is cancelled", () => {
    const annotation = seed(harness.collection, true);

    beginEntityReassign(annotation, harness.ctx, { label: "annotation entity" });
    harness.getPending()?.onCancel();

    expect(harness.collection.find("a1")?.entityId).toBe("old-entity");
    expect(harness.upsertUpdate).not.toHaveBeenCalled();
  });

  // A classification is the one kind whose payload derives from its entity.
  // These go through the options the widget toolbar and the `E` shortcut pass
  // — a label and nothing else — because the rewrite must not depend on the
  // entry point: it used to live in the chip's double-click alone, and the two
  // other ways in saved the previous class under the new entity.
  function seedClassification(collection: AnnotationCollection): LocalAnnotation {
    const annotation: LocalAnnotation = {
      id: "c1",
      entityId: "old-entity",
      kind: "classification",
      viewId: "v1",
      geometry: { labels: ["cat"], confidences: [1] },
      persisted: true,
    };
    collection.add(annotation);
    return annotation;
  }

  it("rewrites a classification's class from the chosen entity, whatever opened the form", () => {
    const annotation = seedClassification(harness.collection);

    beginEntityReassign(annotation, harness.ctx, { label: "annotation entity" });
    harness.getPending()?.onConfirm({ mode: "existing", entityId: "new-entity" });

    expect(harness.collection.find("c1")?.geometry).toMatchObject({ labels: ["picked"] });
    // The update body is built from the live annotation, which is why the
    // rewrite is a write to the collection and not a returned copy.
    const body = harness.upsertUpdate.mock.calls[0][0].body as Record<string, unknown>;
    expect(body.labels).toEqual(["picked"]);
    expect(body.entity_id).toBe("new-entity");
  });

  it("aborts the reassignment when the chosen entity yields no class", () => {
    const annotation = seedClassification(harness.collection);

    beginEntityReassign(annotation, harness.ctx, { label: "annotation entity" });
    harness.getPending()?.onConfirm({ mode: "new", entityFields: { name: "   " } });

    expect(harness.collection.find("c1")?.entityId).toBe("old-entity");
    expect(harness.collection.find("c1")?.geometry).toMatchObject({ labels: ["cat"] });
    expect(harness.upsertUpdate).not.toHaveBeenCalled();
  });

  it("leaves the geometry of a kind that does not derive from its entity alone", () => {
    const annotation = seed(harness.collection, true);

    beginEntityReassign(annotation, harness.ctx, { label: "annotation entity" });
    harness.getPending()?.onConfirm({ mode: "existing", entityId: "new-entity" });

    expect(harness.collection.find("a1")?.geometry).toEqual([0, 0, 0.1, 0.1]);
    expect(harness.upsertUpdate).toHaveBeenCalledTimes(1);
  });
});
