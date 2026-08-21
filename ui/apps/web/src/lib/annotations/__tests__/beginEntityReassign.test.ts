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

  it("lets a kind bring its payload in line before the move is queued", () => {
    const annotation = seed(harness.collection, true);
    // The hook's contract: it *writes*, then says whether to go ahead.
    const syncPayloadToEntity = vi.fn((current: LocalAnnotation) => {
      harness.collection.setGeometry(current.id, [1, 1, 1, 1]);
      return true;
    });

    beginEntityReassign(annotation, harness.ctx, { label: "l", syncPayloadToEntity });
    harness.getPending()?.onConfirm({ mode: "existing", entityId: "new-entity" });

    expect(syncPayloadToEntity).toHaveBeenCalledTimes(1);
    expect(harness.collection.find("a1")?.geometry).toEqual([1, 1, 1, 1]);
    expect(harness.upsertUpdate).toHaveBeenCalledTimes(1);
  });

  it("carries the hook's write into the queued update, not a returned copy", () => {
    const annotation = seed(harness.collection, true);

    beginEntityReassign(annotation, harness.ctx, {
      label: "l",
      syncPayloadToEntity: (current) => {
        harness.collection.setGeometry(current.id, [0.9, 0.9, 0.05, 0.05]);
        return true;
      },
    });
    harness.getPending()?.onConfirm({ mode: "existing", entityId: "new-entity" });

    // The update body is built from the live annotation, which is why writing
    // is the mechanism: a hook that returned a modified copy without touching
    // the collection would type-check and silently change nothing.
    const body = harness.upsertUpdate.mock.calls[0][0].body as Record<string, unknown>;
    expect(body.coords).toEqual([0.9, 0.9, 0.05, 0.05]);
    expect(body.entity_id).toBe("new-entity");
  });

  it("aborts the reassignment when the kind rejects the choice", () => {
    const annotation = seed(harness.collection, true);

    beginEntityReassign(annotation, harness.ctx, {
      label: "l",
      syncPayloadToEntity: () => false,
    });
    harness.getPending()?.onConfirm({ mode: "existing", entityId: "new-entity" });

    expect(harness.collection.find("a1")?.entityId).toBe("old-entity");
    expect(harness.upsertUpdate).not.toHaveBeenCalled();
  });
});
