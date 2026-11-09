/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as THREE from "three";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { BBOX3D_RESOURCE } from "../bbox3dPayloadBuilder.js";
import { BBox3DSession, type PendingConfirm } from "../bbox3dSession.svelte.js";
import type { BoxEditor } from "../boxEditor.svelte.js";
import { realBoxEditor } from "./realBoxEditor.svelte.js";
import {
  AnnotationCollection,
  type AnnotationStore,
  type BBox3DGeometry,
} from "$lib/annotations/annotationCollection.svelte.js";
import { threeQuaternionToLanceRotation } from "$lib/annotations/coordinateTransforms";
import { REVIEW_STATUS } from "$lib/annotations/reviewStatus.js";
import type { LiveAnnotationDraft, SeamContext } from "$lib/annotations/scene/sceneContext.js";
import type { PendingAnnotation, ResourceMutation, Rotation3x3 } from "$lib/annotations/types.js";
import {
  deferred,
  modelBox,
  openManager,
  serveLikeTheApi,
  VIEWPORT,
  widgetSeam,
  type Row,
} from "$lib/workspace/__tests__/workspaceHarness.js";
import type { NextRecordToReview } from "$lib/workspace/reviewGateway.js";
import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

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
  let staged = false;
  let dropStaged: () => void = () => {};
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
    claimStagedWork: (discard) => {
      dropStaged = discard;
      return { set: (value) => (staged = value) };
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
    isStaged: () => staged,
    /** What the record's Discard does to the session's work. */
    dropStaged: () => dropStaged(),
  };
}

// ─── The real box editor ──────────────────────────────────────────────────────
// The untouched-save check compares what the editor reports with the box as
// stored, number for number: only the editor itself can say what it reports.

const editorTeardowns: (() => void)[] = [];

afterEach(() => {
  for (const teardown of editorTeardowns.splice(0)) teardown();
  document.body.innerHTML = "";
});

/** The real box editor wired to the session (`realBoxEditor`), stopped after the test. */
function boxEditorFor(session: BBox3DSession, collection: Pick<AnnotationStore, "byKind">) {
  const wired = realBoxEditor(session, collection);
  editorTeardowns.push(wired.teardown);
  return wired;
}

/** What the editor stages once the box it opened is moved one unit along X. */
function movedOneUnit(opened: PendingConfirm): PendingConfirm {
  const coords = [...opened.coords] as PendingConfirm["coords"];
  coords[0] += 1;
  return { ...opened, coords };
}

/** A turn about the up axis that float32 storage cannot hold exactly. */
const YAW = 0.7;
const COS_YAW = Math.fround(Math.cos(YAW));
const SIN_YAW = Math.fround(Math.sin(YAW));
/** That turn as the dataset gives it back: a row-major matrix of float32 values. */
const STORED_YAW_ROTATION: Rotation3x3 = [COS_YAW, -SIN_YAW, 0, SIN_YAW, COS_YAW, 0, 0, 0, 1];

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

    it("rejects a model's saved box, which deletes it, and says so", () => {
      env.collection.add({
        id: "m1",
        entityId: "e1",
        kind: "bbox3d",
        viewId: "v1",
        geometry: { coords: COORDS, format: "xyzwhd", rotation: ROTATION },
        persisted: true,
        review: { status: "pending", sourceType: "model", sourceName: "detection" },
      });
      session.reportReady(COORDS, ROTATION, "m1");
      expect(session.editingDeleteGesture).toBe("reject");

      session.deleteBox();

      expect(env.updates).toEqual([]);
      expect(env.queued).toHaveLength(1);
      expect(env.queued[0]).toMatchObject({ op: "delete", resource: "bbox3ds", id: "m1" });
      expect(env.collection.find("m1")).toBeUndefined();
      expect(session.confirm).toBeNull();
    });

    it("deletes a person's saved box, and says so", () => {
      addPersisted();
      session.reportReady(COORDS, ROTATION, "b1");

      expect(session.editingDeleteGesture).toBe("delete");
    });

    it("queues a delete for a saved box and drops it from the collection", () => {
      addPersisted();
      session.reportReady(COORDS, ROTATION, "b1");

      session.deleteBox();

      // What the queue held for the box is dropped before its delete is queued.
      expect(env.dropped).toEqual(["b1"]);
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

describe("BBox3DSession staged work", () => {
  let env: ReturnType<typeof makeSeam>;
  let session: BBox3DSession;
  let editor: ReturnType<typeof boxEditorFor>;
  beforeEach(() => {
    env = makeSeam();
    session = new BBox3DSession(env.seam);
    env.collection.add({
      id: "b1",
      entityId: "e1",
      kind: "bbox3d",
      viewId: "v1",
      geometry: { coords: COORDS, format: "xyzwhd", rotation: STORED_YAW_ROTATION },
      persisted: true,
    });
    editor = boxEditorFor(session, env.collection);
  });

  it("holds nothing for a click that only opens a box", () => {
    editor.open("b1");

    expect(session.confirm).not.toBeNull();
    expect(env.isStaged()).toBe(false);
  });

  it("holds a new box", () => {
    session.reportReady(COORDS, ROTATION);

    expect(env.isStaged()).toBe(true);
  });

  const waysOut: [string, (s: BBox3DSession) => void][] = [
    ["saved", (s) => s.save()],
    ["cancelled", (s) => s.cancel()],
    ["deleted", (s) => s.deleteBox()],
    ["moved to another entity", (s) => s.changeEntity()],
    ["dropped by its editor", (s) => s.reportCanceled()],
  ];
  it.each(waysOut)("holds a moved box until it is %s", (_way, leave) => {
    const moved = movedOneUnit(editor.open("b1"));
    session.reportReady(moved.coords, moved.rotation, "b1");
    expect(env.isStaged()).toBe(true);

    leave(session);

    expect(env.isStaged()).toBe(false);
  });

  it("drops a moved box when the record's Discard asks: the HUD and the editor close", () => {
    const moved = movedOneUnit(editor.open("b1"));
    session.reportReady(moved.coords, moved.rotation, "b1");

    env.dropStaged();

    expect(session.confirm).toBeNull();
    expect(env.isStaged()).toBe(false);
    expect(editor.editor.drawPhase).toBe("idle");
    expect(env.updates).toEqual([]);
  });
});

describe("BBox3DSession, a gizmo drag", () => {
  // A gizmo drag is work under way from its press to its release, as a 2D
  // shape's drag is: the session's flag is raised as the editor starts it —
  // on a box a click only opened too — and lowered as it ends, unless it left
  // the HUD a box to save. Discard, Escape or Cancel during it drops it.

  /** How far off the opened box's axes a press on its face lands: on the box, clear of every gizmo. */
  const OFF_AXIS = 1;

  let env: ReturnType<typeof makeSeam>;
  let session: BBox3DSession;
  let wired: ReturnType<typeof boxEditorFor>;
  beforeEach(() => {
    env = makeSeam();
    session = new BBox3DSession(env.seam);
    // Upright, so that two of its rings face the camera edge-on (`grabRing`).
    env.collection.add({
      id: "b1",
      entityId: "e1",
      kind: "bbox3d",
      viewId: "v1",
      geometry: { coords: COORDS, format: "xyzwhd", rotation: ROTATION },
      persisted: true,
    });
    wired = boxEditorFor(session, env.collection);
    wired.open("b1");
  });

  /** Where the arrow `id` of the opened box stands. */
  const arrowAt = (arrows: readonly { id: string; pos: [number, number, number] }[], id: string) =>
    arrows.find((arrow) => arrow.id === id)!.pos;

  /** The drag the editor is in: its phase, and for a move, whether along an axis or on the ground. */
  type Drag = Pick<BoxEditor, "drawPhase" | "moveMode">;
  const dragOf = (editor: BoxEditor): Drag => ({
    drawPhase: editor.drawPhase,
    moveMode: editor.moveMode,
  });

  // Each gizmo of the box, pressed with what would shadow it hidden: seen
  // from the front, a ring seen edge-on crosses the arrows along it.
  const gizmos: [string, Drag, () => { release(): void }][] = [
    ["a rotation ring", { drawPhase: "rotating", moveMode: "ground" }, () => wired.grabRing()],
    [
      "a translate arrow",
      { drawPhase: "moving", moveMode: "axis" },
      () => {
        session.toggleGizmo("rings");
        return wired.grab(arrowAt(wired.editor.translateArrowGizmos, "+x"));
      },
    ],
    [
      "a resize arrow",
      { drawPhase: "resizing-face", moveMode: "ground" },
      () => {
        session.toggleGizmo("rings");
        return wired.grab(arrowAt(wired.editor.arrowGizmos, "+x"));
      },
    ],
    [
      "the box itself",
      { drawPhase: "moving", moveMode: "ground" },
      () => {
        const [x, y, z] = wired.editor.previewCenter;
        return wired.grab([x + OFF_AXIS, y - OFF_AXIS, z]);
      },
    ],
  ];
  it.each(gizmos)(
    "holds the flag while %s is dragged, from its press to its release",
    (_gizmo, drag, press) => {
      expect(env.isStaged()).toBe(false);

      const held = press();
      expect(dragOf(wired.editor)).toEqual(drag);
      expect(env.isStaged()).toBe(true);

      // Let go where it was pressed, the drag changed nothing: the HUD holds nothing.
      held.release();
      expect(wired.editor.drawPhase).toBe("confirming");
      expect(env.isStaged()).toBe(false);
    },
  );

  it("keeps the flag raised once a drag that turned the box is let go: the HUD holds it", () => {
    const ring = wired.grabRing();
    ring.turn();

    ring.release();

    expect(session.confirm?.rotation).not.toEqual(ROTATION);
    expect(env.isStaged()).toBe(true);
  });

  const drops: [string, () => void][] = [
    ["the record's Discard drops it", () => env.dropStaged()],
    [
      "Escape is pressed",
      () => window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })),
    ],
    ["the HUD is cancelled", () => session.cancel()],
  ];
  it.each(drops)(
    "ends a drag that turned the box when %s: let go then, it stages nothing",
    (_way, drop) => {
      const ring = wired.grabRing();
      ring.turn();
      expect(env.isStaged()).toBe(true);

      drop();
      expect(env.isStaged()).toBe(false);
      expect(wired.editor.drawPhase).toBe("idle");
      ring.release();

      expect(session.confirm).toBeNull();
      expect(env.isStaged()).toBe(false);
      expect(env.updates).toEqual([]);
    },
  );
});

describe("BBox3DSession on the real workspace", () => {
  const REC_1 = "rec-1";
  const REC_2 = "rec-2";

  /** A model's 3D box as the dataset holds it: record-wide (no view), turned, float32. */
  function modelBox3D(recordId: string, id: string, overrides: Partial<Row> = {}): Row {
    return {
      ...modelBox(recordId, id),
      view_id: "",
      coords: [...COORDS],
      format: "xyzwhd",
      rotation: [...STORED_YAW_ROTATION],
      is_normalized: false,
      confidence: 0.83,
      ...overrides,
    };
  }

  async function open(
    box: Row = modelBox3D(REC_1, "m1"),
    next: NextRecordToReview | Promise<NextRecordToReview> = { recordId: REC_2, remaining: 1 },
  ) {
    const opened = await openManager(
      {
        [REC_1]: { [BBOX3D_RESOURCE]: [box] },
        [REC_2]: { [BBOX3D_RESOURCE]: [modelBox3D(REC_2, "m2")] },
      },
      { next },
    );
    const seam = widgetSeam(opened.manager, "point-cloud-widget");
    const session = new BBox3DSession(seam);
    const editor = boxEditorFor(session, seam.collection);
    return { ...opened, session, editor };
  }

  const geometryOf = (manager: WorkspaceManager, id: string) =>
    manager.annotations.find(id)!.geometry as BBox3DGeometry;

  it("saves an untouched model box as it is: nothing sent, still pending, Accept still offered", async () => {
    const { manager, session, editor } = await open();
    // The trip through a quaternion does not give the stored rotation back.
    expect(editor.open("m1").rotation).not.toEqual(STORED_YAW_ROTATION);

    session.save();

    expect(manager.pendingCount).toBe(0);
    expect(geometryOf(manager, "m1").rotation).toEqual(STORED_YAW_ROTATION);
    expect(manager.annotations.find("m1")?.review?.status).toBe(REVIEW_STATUS.PENDING);
    expect(manager.review.accept("m1")).toBe(true);
  });

  it("saves an untouched box stored as corners, turned, as it is", async () => {
    const corners = modelBox3D(REC_1, "m1", { coords: [0, 0, 0, 2, 4, 6], format: "xyzxyz" });
    const { manager, session, editor } = await open(corners);
    editor.open("m1");

    session.save();

    expect(manager.pendingCount).toBe(0);
    expect(manager.annotations.find("m1")?.review?.status).toBe(REVIEW_STATUS.PENDING);
    expect(geometryOf(manager, "m1")).toEqual({
      format: "xyzxyz",
      coords: [0, 0, 0, 2, 4, 6],
      rotation: STORED_YAW_ROTATION,
    });
  });

  it("sends only the move of a moved box: its own rotation and view stay as stored", async () => {
    const { manager, session, editor, backend } = await open();
    serveLikeTheApi(backend, REC_1);
    const moved = movedOneUnit(editor.open("m1"));
    session.reportReady(moved.coords, moved.rotation, "m1");

    // The HUD's Apply stages the move into the record's unsaved work: the box
    // stays in review until the workspace's Save, which stores it accepted.
    session.save();
    expect(manager.annotations.find("m1")?.review?.status).toBe(REVIEW_STATUS.PENDING);
    expect(manager.review.rows.find((row) => row.id === "m1")?.canAccept).toBe(true);
    expect(await manager.flushSave()).toBe(true);
    expect(manager.annotations.find("m1")?.review?.status).toBe(REVIEW_STATUS.ACCEPTED);

    const sent = backend.writes.find((w) => w.op === "update");
    expect(sent?.op === "update" ? sent.body : undefined).toMatchObject({
      coords: moved.coords,
      rotation: STORED_YAW_ROTATION,
      view_id: "",
      format: "xyzwhd",
    });
  });

  it("sends the rotation a box was turned to", async () => {
    const { manager, session, editor, backend } = await open();
    const opened = editor.open("m1");
    const turned = threeQuaternionToLanceRotation(
      new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), YAW / 2),
    );
    session.reportReady(opened.coords, turned, "m1");

    session.save();
    await manager.flushSave();

    const sent = backend.writes.find((w) => w.op === "update");
    expect(sent?.op === "update" ? sent.body.rotation : undefined).toEqual(turned);
  });

  it("Save & next stays on a record whose HUD holds a moved box, and moves once it is saved", async () => {
    const { manager, session, editor, backend } = await open();
    const moved = movedOneUnit(editor.open("m1"));
    session.reportReady(moved.coords, moved.rotation, "m1");

    await manager.review.saveAndNext(VIEWPORT);
    expect(manager.recordId).toBe(REC_1);
    expect(manager.review.outcome).toEqual({ kind: "not-saved" });
    expect(backend.writes).toEqual([]);

    session.save();
    await manager.review.saveAndNext(VIEWPORT);
    expect(manager.recordId).toBe(REC_2);
    expect(backend.writes.map((w) => w.op === "update" && w.id)).toEqual(["m1"]);
  });

  it("Save & next stays on a record whose HUD holds a new box, and moves once it is cancelled", async () => {
    const { manager, session } = await open();
    session.reportReady(COORDS, ROTATION);

    await manager.review.saveAndNext(VIEWPORT);
    expect(manager.recordId).toBe(REC_1);

    session.cancel();
    await manager.review.saveAndNext(VIEWPORT);
    expect(manager.recordId).toBe(REC_2);
  });

  it("Save & next is not held by a HUD a click only opened", async () => {
    const { manager, editor } = await open();
    editor.open("m1");

    await manager.review.saveAndNext(VIEWPORT);

    expect(manager.recordId).toBe(REC_2);
  });

  it("Discard closes a HUD holding a moved box, and puts the box back as stored", async () => {
    const { manager, session, editor } = await open();
    const moved = movedOneUnit(editor.open("m1"));
    session.reportReady(moved.coords, moved.rotation, "m1");
    expect(manager.review.canDiscard).toBe(true);

    await manager.review.discard();

    expect(session.confirm).toBeNull();
    expect(editor.editor.drawPhase).toBe("idle");
    expect(manager.hasUnsavedWork).toBe(false);
    expect(geometryOf(manager, "m1").coords).toEqual(COORDS);
  });

  it("rejects nothing while Save & next runs: the HUD says so and stays open", async () => {
    const lookup = deferred<NextRecordToReview>();
    const { manager, session, editor, backend } = await open(undefined, lookup.promise);
    editor.open("m1");

    const moving = manager.review.saveAndNext(VIEWPORT);
    await expect.poll(() => backend.log).toContain("nextRecordToReview");
    expect(session.editingDeleteGesture).toBe("locked");
    session.deleteBox();

    expect(session.confirm?.editingId).toBe("m1");
    expect(manager.annotations.find("m1")?.review?.status).toBe(REVIEW_STATUS.PENDING);
    expect(manager.pendingCount).toBe(0);
    lookup.resolve({ recordId: null, remaining: 0 });
    await moving;

    // Once it is over, the HUD rejects again.
    expect(session.editingDeleteGesture).toBe("reject");
  });

  describe("a gizmo drag on a box a click only opened", () => {
    /** The model's box upright, so that its rings can be grabbed (`grabRing`). */
    const upright = () => modelBox3D(REC_1, "m1", { rotation: [...ROTATION] });

    it("keeps Save & next on the record while it runs, and lets it move once let go", async () => {
      const { manager, editor } = await open(upright());
      editor.open("m1");
      const ring = editor.grabRing();

      await manager.review.saveAndNext(VIEWPORT);
      expect(manager.recordId).toBe(REC_1);
      expect(manager.review.outcome).toEqual({ kind: "not-saved" });

      ring.release();
      await manager.review.saveAndNext(VIEWPORT);
      expect(manager.recordId).toBe(REC_2);
    });

    it("begun while Save & next looks for the next record, keeps the reviewer on the record", async () => {
      const lookup = deferred<NextRecordToReview>();
      const { manager, editor, backend } = await open(upright(), lookup.promise);
      editor.open("m1");

      const moving = manager.review.saveAndNext(VIEWPORT);
      await expect.poll(() => backend.log).toContain("nextRecordToReview");
      const ring = editor.grabRing();
      lookup.resolve({ recordId: REC_2, remaining: 1 });
      await moving;

      expect(manager.recordId).toBe(REC_1);
      expect(manager.review.outcome).toEqual({ kind: "not-saved" });
      expect(editor.editor.drawPhase).toBe("rotating");
      ring.release();
    });

    it("counts as one unsaved item while it runs, and as none once let go where it began", async () => {
      const { manager, editor } = await open(upright());
      editor.open("m1");
      expect(manager.unsavedCount).toBe(0);

      const ring = editor.grabRing();
      expect(manager.unsavedCount).toBe(1);

      ring.release();
      expect(manager.unsavedCount).toBe(0);
    });

    it("counts once with the box the HUD holds: one box, one unsaved item", async () => {
      const { manager, editor } = await open(upright());
      editor.open("m1");
      const turning = editor.grabRing();
      turning.turn();
      turning.release();
      expect(manager.unsavedCount).toBe(1);

      // A quarter turn about the camera's axis leaves two rings edge-on again.
      const again = editor.grabRing();
      expect(manager.unsavedCount).toBe(1);
      again.release();
      expect(manager.unsavedCount).toBe(1);
    });

    it("is dropped by Discard, HUD and all: let go then, it stages nothing", async () => {
      const { manager, session, editor } = await open(upright());
      editor.open("m1");
      const ring = editor.grabRing();
      ring.turn();
      expect(manager.review.canDiscard).toBe(true);

      await manager.review.discard();
      expect(session.confirm).toBeNull();
      expect(editor.editor.drawPhase).toBe("idle");
      ring.release();

      expect(session.confirm).toBeNull();
      expect(manager.hasUnsavedWork).toBe(false);
      expect(manager.pendingCount).toBe(0);
      expect(geometryOf(manager, "m1").rotation).toEqual(ROTATION);
    });
  });
});
