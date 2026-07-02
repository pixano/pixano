/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  AnnotationCollection,
  type BBox3DGeometry,
  type BBoxGeometry,
} from "../annotationCollection.svelte.js";
import {
  commitGeometryEdit,
  commitNewAnnotation,
  type CommitContext,
} from "../payloadBuilders.js";
import type { ResourceMutation } from "../types.js";

const BUILD_CTX = { datasetId: "ds-1", recordId: "rec-1", viewId: "view-1" };

/** A CommitContext over a real collection with a recording MutationSink. */
function makeCtx() {
  const collection = new AnnotationCollection();
  const queued: ResourceMutation[] = [];
  const updates: Extract<ResourceMutation, { op: "update" }>[] = [];
  const patches: { id: string; resource: string; patch: Record<string, unknown> }[] = [];

  const ctx: CommitContext = {
    buildContext: BUILD_CTX,
    collection,
    widgetId: "widget-1",
    mutations: {
      get pending() {
        return queued;
      },
      queue: (m) => queued.push(m),
      upsertUpdate: (m) => updates.push(m),
      patchPendingCreate: (id, resource, patch) => patches.push({ id, resource, patch }),
      dropForLocalAnnotation: () => {},
    },
  };
  return { ctx, collection, queued, updates, patches };
}

describe("commitNewAnnotation", () => {
  it("adds a draft (persisted:false) carrying the kind, geometry and view", () => {
    const { ctx, collection } = makeCtx();
    const geometry: BBoxGeometry = [0.1, 0.2, 0.3, 0.4];

    const ann = commitNewAnnotation(ctx, "bbox", geometry);

    expect(collection.items).toHaveLength(1);
    expect(collection.items[0].id).toBe(ann.id);
    expect(ann.kind).toBe("bbox");
    expect(ann.persisted).toBe(false);
    expect(ann.viewId).toBe("view-1");
    expect(ann.geometry).toEqual(geometry);
  });

  it("queues the kind's create mutations (entity before annotation)", () => {
    const { ctx, queued } = makeCtx();

    const ann = commitNewAnnotation(ctx, "bbox", [0, 0, 1, 1]);

    expect(queued.map((m) => [m.op, m.resource])).toEqual([
      ["create", "entities"],
      ["create", "bboxes"],
    ]);
    // Every queued mutation is tagged with the new annotation for later reconcile.
    expect(queued.every((m) => m.localAnnotationId === ann.id)).toBe(true);
  });

  it("uses caller-supplied ids when given (e.g. reusing an existing entity)", () => {
    const { ctx } = makeCtx();

    const ann = commitNewAnnotation(ctx, "bbox", [0, 0, 1, 1], {
      id: "fixed-id",
      entityId: "fixed-entity",
    });

    expect(ann.id).toBe("fixed-id");
    expect(ann.entityId).toBe("fixed-entity");
  });

  it("works for a 3D kind, forwarding rotation into the create body", () => {
    const { ctx, queued } = makeCtx();
    const geometry: BBox3DGeometry = {
      coords: [1, 2, 3, 4, 5, 6],
      format: "xyzwhd",
      rotation: [1, 0, 0, 0, 1, 0, 0, 0, 1],
    };

    commitNewAnnotation(ctx, "bbox3d", geometry);

    const create = queued.find((m) => m.resource === "bbox3ds");
    expect(create?.op).toBe("create");
    const body = (create as Extract<ResourceMutation, { op: "create" }>).body;
    expect(body.coords).toEqual([1, 2, 3, 4, 5, 6]);
    expect(body.rotation).toEqual([1, 0, 0, 0, 1, 0, 0, 0, 1]);
  });
});

describe("commitGeometryEdit", () => {
  it("on a persisted annotation: writes the geometry and queues an update", () => {
    const { ctx, collection, updates, patches } = makeCtx();
    collection.add({
      id: "a1",
      entityId: "e1",
      kind: "bbox",
      viewId: "view-1",
      geometry: [0, 0, 0.5, 0.5] as BBoxGeometry,
      persisted: true,
    });

    commitGeometryEdit(ctx, "a1", [0.2, 0.2, 0.6, 0.6] as BBoxGeometry);

    expect(collection.find("a1")?.geometry).toEqual([0.2, 0.2, 0.6, 0.6]);
    expect(patches).toHaveLength(0);
    expect(updates).toHaveLength(1);
    expect(updates[0]).toMatchObject({
      op: "update",
      resource: "bboxes",
      id: "a1",
      localAnnotationId: "a1",
    });
    expect(updates[0].body.coords).toEqual([0.2, 0.2, 0.6, 0.6]);
  });

  it("on a draft: patches the pending create, changing only the geometry", () => {
    const { ctx, collection, updates, patches } = makeCtx();
    collection.add({
      id: "draft1",
      entityId: "e1",
      kind: "bbox",
      viewId: "view-1",
      geometry: [0, 0, 0.5, 0.5] as BBoxGeometry,
      persisted: false,
    });

    commitGeometryEdit(ctx, "draft1", [0.3, 0.3, 0.4, 0.4] as BBoxGeometry);

    expect(updates).toHaveLength(0);
    expect(patches).toHaveLength(1);
    expect(patches[0].id).toBe("draft1");
    expect(patches[0].resource).toBe("bboxes");
    // The D9 invariant: the patch carries the new geometry (and only same-valued
    // fields otherwise), so merging it into the queued create changes geometry only.
    expect(patches[0].patch.coords).toEqual([0.3, 0.3, 0.4, 0.4]);
  });

  it("is a no-op when the annotation id is unknown", () => {
    const { ctx, updates, patches } = makeCtx();

    expect(() => commitGeometryEdit(ctx, "missing", [0, 0, 1, 1] as BBoxGeometry)).not.toThrow();
    expect(updates).toHaveLength(0);
    expect(patches).toHaveLength(0);
  });
});
