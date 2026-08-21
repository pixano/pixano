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

  it("leaves everything alone when the form is cancelled", () => {
    const annotation = seed(harness.collection, true);

    beginEntityReassign(annotation, harness.ctx, { label: "annotation entity" });
    harness.getPending()?.onCancel();

    expect(harness.collection.find("a1")?.entityId).toBe("old-entity");
    expect(harness.upsertUpdate).not.toHaveBeenCalled();
  });

  it("lets a kind rewrite its payload to match the chosen entity", () => {
    const annotation = seed(harness.collection, true);
    const adapt = vi.fn((current: LocalAnnotation) => ({ ...current, geometry: [1, 1, 1, 1] }));

    beginEntityReassign(annotation, harness.ctx, { label: "l", adapt });
    harness.getPending()?.onConfirm({ mode: "existing", entityId: "new-entity" });

    expect(adapt).toHaveBeenCalledTimes(1);
    expect(harness.upsertUpdate).toHaveBeenCalledTimes(1);
  });

  it("aborts the reassignment when the kind rejects the choice", () => {
    const annotation = seed(harness.collection, true);

    beginEntityReassign(annotation, harness.ctx, { label: "l", adapt: () => null });
    harness.getPending()?.onConfirm({ mode: "existing", entityId: "new-entity" });

    expect(harness.collection.find("a1")?.entityId).toBe("old-entity");
    expect(harness.upsertUpdate).not.toHaveBeenCalled();
  });
});
