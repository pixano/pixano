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
  reassignEntity,
  type DraftCommitContext,
  type ReassignEntityContext,
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

describe("reassignEntity (change a persisted annotation's entity)", () => {
  function makePersisted(): LocalBBox3DAnnotation {
    return {
      id: "box-1",
      entityId: "old-ent",
      kind: "bbox3d",
      viewId: "",
      geometry: { coords: [0, 0, 0, 1, 1, 1], format: "xyzwhd" },
      persisted: true,
    };
  }

  function makeCtx(collection: AnnotationCollection, findEntity = vi.fn()): ReassignEntityContext {
    return {
      collection,
      mutations: { queue: vi.fn(), upsertUpdate: vi.fn() },
      buildContext: CTX,
      widgetId: "w1",
      findEntity,
      requestRedraw: vi.fn(),
    };
  }

  it("existing entity: repoints the box and upserts a single update, no create", () => {
    const collection = new AnnotationCollection([makePersisted()]);
    const findEntity = vi.fn().mockReturnValue({ id: "new-ent", category: "bus" });
    const ctx = makeCtx(collection, findEntity);

    reassignEntity(collection.find("box-1")!, { mode: "existing", entityId: "new-ent" }, ctx);

    expect(collection.find("box-1")!.entityId).toBe("new-ent");
    expect(ctx.mutations.queue).not.toHaveBeenCalled();
    expect(ctx.mutations.upsertUpdate).toHaveBeenCalledTimes(1);
    expect(ctx.mutations.upsertUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ op: "update", resource: "bbox3ds", id: "box-1" }),
    );
    expect(vi.mocked(ctx.mutations.upsertUpdate).mock.calls[0][0].body).toMatchObject({ entity_id: "new-ent" });
  });

  it("new entity: queues an entity create + the box update with the generated id", () => {
    const collection = new AnnotationCollection([makePersisted()]);
    const ctx = makeCtx(collection);

    reassignEntity(collection.find("box-1")!, { mode: "new", entityFields: { category: "car" } }, ctx);

    const box = collection.find("box-1")!;
    expect(box.entityId).not.toBe("old-ent");
    expect(box.entity).toMatchObject({ category: "car" });
    expect(ctx.mutations.queue).toHaveBeenCalledTimes(1); // the new entity create
    expect(ctx.mutations.queue).toHaveBeenCalledWith(
      expect.objectContaining({ op: "create", resource: "entities" }),
    );
    expect(ctx.mutations.upsertUpdate).toHaveBeenCalledTimes(1);
  });

  it("ignores a non-persisted (draft) annotation", () => {
    const draft = { ...makePersisted(), persisted: false };
    const collection = new AnnotationCollection([draft]);
    const ctx = makeCtx(collection);

    reassignEntity(collection.find("box-1")!, { mode: "existing", entityId: "new-ent" }, ctx);

    expect(ctx.mutations.queue).not.toHaveBeenCalled();
    expect(ctx.mutations.upsertUpdate).not.toHaveBeenCalled();
    expect(collection.find("box-1")!.entityId).toBe("old-ent");
  });
});
