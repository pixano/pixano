/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import { AnnotationCollection } from "../annotationCollection.svelte.js";
import type { LocalBBox, LocalBBox3DAnnotation } from "../annotationCollection.svelte.js";
import {
  buildDeleteMutations,
  commitDraftWithEntity,
  payloadBuilderFor,
  type DraftCommitContext,
} from "../payloadBuilders.js";

const CTX = { datasetId: "ds", recordId: "rec", viewId: "view" };

const BBOX: LocalBBox = {
  id: "ann-1",
  entityId: "ent-1",
  kind: "bbox",
  viewId: "view",
  geometry: [0.1, 0.2, 0.3, 0.4],
  persisted: false,
};

const BBOX3D: LocalBBox3DAnnotation = {
  id: "ann-3d",
  entityId: "ent-3d",
  kind: "bbox3d",
  viewId: "",
  geometry: { coords: [1, 2, 3, 4, 5, 6], format: "xyzwhd", rotation: [1, 0, 0, 0, 1, 0, 0, 0, 1] },
  persisted: false,
};

describe("payloadBuilderFor", () => {
  it("resolves a builder per registered kind and throws for unknown kinds", () => {
    expect(payloadBuilderFor("bbox").resource).toBe("bboxes");
    expect(payloadBuilderFor("bbox3d").resource).toBe("bbox3ds");
    expect(() => payloadBuilderFor("mask")).toThrow(/mask/);
  });
});

describe("bbox payload builder", () => {
  it("buildCreate pairs an entity create with the bbox create, reusing the local ids", () => {
    const mutations = payloadBuilderFor("bbox").buildCreate(CTX, BBOX, "w1");

    expect(mutations).toHaveLength(2);
    const [entity, bbox] = mutations;
    expect(entity).toMatchObject({ op: "create", resource: "entities" });
    expect((entity as { body: Record<string, unknown> }).body.id).toBe("ent-1");
    expect(bbox).toMatchObject({
      op: "create",
      resource: "bboxes",
      widgetId: "w1",
      localAnnotationId: "ann-1",
    });
    // The backend row id is the local annotation id, so post-save edits target the right row.
    expect((bbox as { body: Record<string, unknown> }).body.id).toBe("ann-1");
    expect((bbox as { body: Record<string, unknown> }).body.coords).toEqual([0.1, 0.2, 0.3, 0.4]);
  });

  it("buildUpdate produces the update body from the annotation", () => {
    const body = payloadBuilderFor("bbox").buildUpdate(CTX, BBOX);
    expect(body).toMatchObject({ id: "ann-1", entity_id: "ent-1", coords: [0.1, 0.2, 0.3, 0.4] });
  });
});

describe("bbox3d payload builder", () => {
  it("buildCreate carries coords and rotation, reusing the local ids", () => {
    const mutations = payloadBuilderFor("bbox3d").buildCreate(CTX, BBOX3D, "w1");

    expect(mutations).toHaveLength(2);
    const bbox3d = mutations[1] as { body: Record<string, unknown> };
    expect(bbox3d.body.id).toBe("ann-3d");
    expect(bbox3d.body.coords).toEqual([1, 2, 3, 4, 5, 6]);
    expect(bbox3d.body.rotation).toEqual([1, 0, 0, 0, 1, 0, 0, 0, 1]);
  });
});

describe("buildDeleteMutations", () => {
  it("deletes only the annotation row; the orphan entity is pruned server-side", () => {
    const mutations = buildDeleteMutations(BBOX, "w1");
    expect(mutations).toEqual([
      expect.objectContaining({ op: "delete", resource: "bboxes", id: "ann-1", localAnnotationId: "ann-1" }),
    ]);
  });
});

describe("commitDraftWithEntity (shared draft-commit)", () => {
  function makeDraft(): LocalBBox {
    return { id: "d1", entityId: "", kind: "bbox", viewId: "view", geometry: [0, 0, 1, 1], persisted: false };
  }

  function makeCtx(collection: AnnotationCollection, findEntity = vi.fn()): DraftCommitContext {
    return {
      collection,
      mutations: { queue: vi.fn() },
      buildContext: CTX,
      widgetId: "w1",
      findEntity,
      requestRedraw: vi.fn(),
    };
  }

  it("new entity: assigns a generated id + field snapshot and queues entity + bbox creates", () => {
    const collection = new AnnotationCollection([makeDraft()]);
    const ctx = makeCtx(collection);

    commitDraftWithEntity(collection.find("d1")!, { mode: "new", entityFields: { category: "car" } }, ctx);

    const draft = collection.find("d1")!;
    expect(draft.entityId).not.toBe("");
    expect(draft.entity).toMatchObject({ category: "car" });
    expect(ctx.mutations.queue).toHaveBeenCalledTimes(2); // entity + bbox
    expect(ctx.requestRedraw).toHaveBeenCalled();
  });

  it("existing entity: reuses the id, snapshots via findEntity, and queues only the bbox create", () => {
    const collection = new AnnotationCollection([makeDraft()]);
    const findEntity = vi.fn().mockReturnValue({ id: "ent-9", category: "bus" });
    const ctx = makeCtx(collection, findEntity);

    commitDraftWithEntity(collection.find("d1")!, { mode: "existing", entityId: "ent-9" }, ctx);

    const draft = collection.find("d1")!;
    expect(draft.entityId).toBe("ent-9");
    expect(draft.entity).toMatchObject({ category: "bus" });
    expect(findEntity).toHaveBeenCalledWith("ent-9");
    expect(ctx.mutations.queue).toHaveBeenCalledTimes(1); // bbox only; entity already exists
  });
});
