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
import type { LiveAnnotationDraft, SeamContext } from "$lib/annotations/scene/sceneContext.js";
import type { PendingAnnotation, ResourceMutation, Rotation3x3 } from "$lib/annotations/types.js";

const COORDS: [number, number, number, number, number, number] = [1, 2, 3, 4, 5, 6];
const ROTATION: Rotation3x3 = [1, 0, 0, 0, 1, 0, 0, 0, 1];

function makeSeam() {
  const collection = new AnnotationCollection();
  const queued: ResourceMutation[] = [];
  const updates: Extract<ResourceMutation, { op: "update" }>[] = [];
  const entities: Record<string, Record<string, unknown>> = {};
  const dropped: string[] = [];
  let pending: PendingAnnotation | null = null;
  let liveDraft: LiveAnnotationDraft | null = null;
  const seam: SeamContext = {
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
      dropForLocalAnnotation: (id) => dropped.push(id),
      dropPendingEntityCreate: () => {},
    },
    // Mirrors buildSeam: publish stamps this widget, clear only clears its own.
    liveDraft: {
      get: () => liveDraft,
      publish: (draft) => (liveDraft = { ...draft, sourceWidgetId: "w1" }),
      clear: () => {
        if (liveDraft?.sourceWidgetId === "w1") liveDraft = null;
      },
    },
    setActiveTool: () => {},
    requestRedraw: () => {},
    beginPendingAnnotation: (p) => (pending = p),
    findEntity: (id) => entities[id],
    isEntityVisible: () => true,
  };
  return {
    seam,
    collection,
    queued,
    updates,
    entities,
    dropped,
    getPending: () => pending,
    getLiveDraft: () => liveDraft,
  };
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

  it("reportPreview broadcasts a live bbox3d draft through the seam", () => {
    session.reportPreview(COORDS, ROTATION);
    expect(env.getLiveDraft()).toEqual({
      kind: "bbox3d",
      geometry: { coords: COORDS, format: "xyzwhd", rotation: ROTATION },
      editingId: null,
      sourceWidgetId: "w1",
    });
  });

  it("reportPreview carries the id of the box being edited", () => {
    session.reportPreview(COORDS, ROTATION, "b1");
    expect(env.getLiveDraft()?.editingId).toBe("b1");
  });

  it("clearPreview clears this widget's own draft", () => {
    session.reportPreview(COORDS, ROTATION);
    session.clearPreview();
    expect(env.getLiveDraft()).toBeNull();
  });

  // Both of these are commit paths that write to the mutation queue, and both
  // were shipped untested (see DEBT-4).
  describe("deleteBox", () => {
    function addPersisted(id = "b1") {
      env.collection.add({
        id,
        entityId: "e1",
        kind: "bbox3d",
        viewId: "v1",
        geometry: { coords: COORDS, format: "xyzwhd", rotation: ROTATION },
        persisted: true,
      });
    }

    it("queues a delete for a saved box and drops it from the collection", () => {
      addPersisted();
      session.reportReady(COORDS, ROTATION, "b1");

      session.deleteBox();

      expect(env.queued).toHaveLength(1);
      expect(env.queued[0]).toMatchObject({ op: "delete", resource: "bbox3ds", id: "b1" });
      expect(env.collection.find("b1")).toBeUndefined();
      expect(session.confirm).toBeNull();
      expect(resetCalls).toBe(1);
    });

    // An unsaved box has no backend row yet, so deleting it must cancel its
    // queued creates rather than queue a delete for something that never existed.
    it("drops the pending creates for an unsaved box instead of queueing a delete", () => {
      session.reportReady(COORDS, ROTATION);
      session.save(); // stages an unsaved draft, defers the create
      const draftId = env.collection.items[0].id;
      session.reportReady(COORDS, ROTATION, draftId);

      session.deleteBox();

      expect(env.queued.filter((m) => m.op === "delete")).toHaveLength(0);
      expect(env.dropped).toEqual([draftId]);
      expect(env.collection.find(draftId)).toBeUndefined();
    });

    it("is a no-op when no box is being edited", () => {
      addPersisted();
      session.deleteBox();

      expect(env.queued).toHaveLength(0);
      expect(env.collection.count).toBe(1);
      expect(resetCalls).toBe(0);
    });

    it("is a no-op when the edited box is no longer in the collection", () => {
      session.reportReady(COORDS, ROTATION, "gone");

      session.deleteBox();

      expect(env.queued).toHaveLength(0);
      expect(session.confirm).toBeNull();
    });
  });

  describe("changeEntity", () => {
    function addPersisted() {
      env.collection.add({
        id: "b1",
        entityId: "e1",
        kind: "bbox3d",
        viewId: "v1",
        geometry: { coords: COORDS, format: "xyzwhd", rotation: ROTATION },
        persisted: true,
      });
    }

    it("opens the entity picker and reassigns the box on confirm", () => {
      addPersisted();
      env.entities["e2"] = { id: "e2", category: "bus" };
      session.reportReady(COORDS, ROTATION, "b1");

      session.changeEntity();

      expect(session.confirm).toBeNull();
      expect(resetCalls).toBe(1);
      env.getPending()!.onConfirm({ mode: "existing", entityId: "e2" });
      expect(env.collection.find("b1")?.entityId).toBe("e2");
      expect(env.updates).toHaveLength(1);
      expect(env.updates[0].id).toBe("b1");
    });

    // Reassignment only makes sense once the box has an entity to move away from.
    it("is a no-op for a box that has not been saved yet", () => {
      env.collection.add({
        id: "draft",
        entityId: "",
        kind: "bbox3d",
        viewId: "v1",
        geometry: { coords: COORDS, format: "xyzwhd", rotation: ROTATION },
        persisted: false,
      });
      session.reportReady(COORDS, ROTATION, "draft");

      session.changeEntity();

      expect(env.getPending()).toBeNull();
      expect(session.confirm).not.toBeNull();
      expect(resetCalls).toBe(0);
    });

    it("is a no-op when no box is being edited", () => {
      addPersisted();
      session.changeEntity();

      expect(env.getPending()).toBeNull();
      expect(resetCalls).toBe(0);
    });
  });

  it("toggleGizmo flips a visibility key", () => {
    expect(session.gizmoVisibility.rings).toBe(true);
    session.toggleGizmo("rings");
    expect(session.gizmoVisibility.rings).toBe(false);
    expect(session.gizmoVisibility.resizeArrows).toBe(true);
  });
});
