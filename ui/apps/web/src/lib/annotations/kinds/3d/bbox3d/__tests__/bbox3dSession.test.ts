/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { beforeEach, describe, expect, it } from "vitest";

import { BBox3DSession } from "../bbox3dSession.svelte.js";
import {
  AnnotationCollection,
  type BBox3DGeometry,
} from "$lib/annotations/annotationCollection.svelte.js";
import type { SceneContextBase } from "$lib/annotations/scene/sceneContext.js";
import type { PendingAnnotation, ResourceMutation } from "$lib/annotations/types.js";

const COORDS: [number, number, number, number, number, number] = [1, 2, 3, 4, 5, 6];
const ROTATION = [1, 0, 0, 0, 1, 0, 0, 0, 1];

function makeSeam() {
  const collection = new AnnotationCollection();
  const queued: ResourceMutation[] = [];
  const updates: Extract<ResourceMutation, { op: "update" }>[] = [];
  const entities: Record<string, Record<string, unknown>> = {};
  let pending: PendingAnnotation | null = null;
  const seam: SceneContextBase = {
    widgetId: "w1",
    buildContext: { datasetId: "ds", recordId: "rec", viewId: "v1" },
    collection,
    mutations: {
      get pending() {
        return queued;
      },
      queue: (m) => queued.push(m),
      upsertUpdate: (m) => updates.push(m),
      patchPendingCreate: () => {},
      dropForLocalAnnotation: () => {},
    },
    setActiveTool: () => {},
    requestRedraw: () => {},
    beginPendingAnnotation: (p) => (pending = p),
    findEntity: (id) => entities[id],
    isEntityVisible: () => true,
  };
  return { seam, collection, queued, updates, entities, getPending: () => pending };
}

describe("BBox3DSession", () => {
  let env: ReturnType<typeof makeSeam>;
  let session: BBox3DSession;
  let resetCalls: number;
  beforeEach(() => {
    env = makeSeam();
    session = new BBox3DSession(env.seam);
    resetCalls = 0;
    session.setResetEditor(() => (resetCalls += 1));
  });

  it("reportReady stages a confirm; reportCanceled clears it", () => {
    session.reportReady(COORDS, ROTATION);
    expect(session.confirm).toEqual({ coords: COORDS, rotation: ROTATION, editingId: undefined });
    session.reportCanceled();
    expect(session.confirm).toBeNull();
  });

  it("save() on a new draft stages an unsaved box and defers the create to entity confirm", () => {
    session.reportReady(COORDS, ROTATION);
    session.save();

    // The box is shown right away as an unsaved draft with no entity yet, but no
    // mutations are queued until the user confirms the entity in the Inspector.
    expect(env.collection.count).toBe(1);
    expect(env.collection.items[0].kind).toBe("bbox3d");
    expect(env.collection.items[0].persisted).toBe(false);
    expect(env.collection.items[0].entityId).toBe("");
    expect(env.queued).toHaveLength(0);
    expect(session.confirm).toBeNull();
    expect(resetCalls).toBe(1);

    // Confirming with a new entity queues the entity + bbox creates.
    env.getPending()!.onConfirm({ mode: "new", entityFields: { category: "car" } });
    expect(env.queued.map((m) => m.resource)).toEqual(["entities", "bbox3ds"]);
  });

  it("save() on an edit commits an update to the existing box", () => {
    env.collection.add({
      id: "b1",
      entityId: "e1",
      kind: "bbox3d",
      viewId: "v1",
      geometry: {
        coords: [0, 0, 0, 1, 1, 1],
        format: "xyzwhd",
        rotation: ROTATION,
      } as BBox3DGeometry,
      persisted: true,
    });
    session.reportReady(COORDS, ROTATION, "b1");
    session.save();

    expect(env.updates).toHaveLength(1);
    expect(env.updates[0].id).toBe("b1");
    expect(env.collection.find("b1")?.geometry).toMatchObject({ coords: COORDS });
    expect(session.confirm).toBeNull();
    expect(resetCalls).toBe(1);
  });

  it("cancel() resets the editor and commits nothing", () => {
    session.reportReady(COORDS, ROTATION);
    session.cancel();

    expect(session.confirm).toBeNull();
    expect(env.collection.count).toBe(0);
    expect(env.queued).toHaveLength(0);
    expect(resetCalls).toBe(1);
  });

  it("save() with nothing pending is a no-op", () => {
    session.save();
    expect(env.collection.count).toBe(0);
    expect(env.queued).toHaveLength(0);
    expect(resetCalls).toBe(0);
  });

  it("toggleGizmo flips a visibility key", () => {
    expect(session.gizmoVisibility.rings).toBe(true);
    session.toggleGizmo("rings");
    expect(session.gizmoVisibility.rings).toBe(false);
    expect(session.gizmoVisibility.resizeArrows).toBe(true);
  });
});
