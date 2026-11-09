/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { flushSync } from "svelte";
import { describe, expect, it, vi } from "vitest";

import type { WorkspaceManager } from "../workspaceManager.svelte.js";
import type { WorkspaceSession } from "../workspaceSession.svelte.js";
import {
  DATASET_ID,
  deferred,
  drag,
  entityOf,
  geometryOf,
  humanBox,
  MODEL_METADATA,
  modelBox,
  modelMask,
  MOVED,
  openManager,
  openWithBoxes,
  REC,
  rowOf,
  serveLikeTheApi,
  statusOf,
  STORED,
  updatesSent,
  viewIdOf,
  VIEWPORT,
  widgetSeam,
  type Row,
} from "./workspaceHarness.js";
import type {
  BBoxGeometry,
  LocalAnnotation,
} from "$lib/annotations/annotationCollection.svelte.js";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import { CLASSIFICATION_RESOURCE } from "$lib/annotations/kinds/2d/classification/classificationPayloadBuilder.js";
import { MASK_RESOURCE } from "$lib/annotations/kinds/2d/mask/maskPayloadBuilder.js";
import { BBOX3D_RESOURCE } from "$lib/annotations/kinds/3d/bbox3d/bbox3dPayloadBuilder.js";
import { BBox3DSession } from "$lib/annotations/kinds/3d/bbox3d/bbox3dSession.svelte.js";
import {
  beginEntityReassign,
  deleteGestureFor,
  deleteLocalAnnotation,
  reassignEntity,
} from "$lib/annotations/payloadBuilders.js";
import {
  HUMAN_REVIEW_FILTER,
  REVIEW_STATUS,
  type ReviewFilterKey,
} from "$lib/annotations/reviewStatus.js";
import type { Scene2DContext, SeamContext } from "$lib/annotations/scene/sceneContext.js";
import { selectTool2D } from "$lib/annotations/scene/selectTool2D.js";
import type { Rotation3x3 } from "$lib/annotations/types.js";

// Every decision sequence the review allows — Accept, Reject, an edit of a
// model's annotation, a delete, which is its Reject —, and what the review
// status chips let a widget display, run through the real workspace — manager,
// review controller, mutation queue, commit helpers, the seam, the select tool
// — and asserted on what the screen shows and on what reaches the backend when
// the person presses Save. The queue keeps one pending update per row, so an
// Accept and an edit of one row riding in one update is a property of what is
// sent, not of the local state alone. What a save does with work begun during
// it is in saveScenarios.svelte.test.ts.

/**
 * The session the manager holds, where the status chips write the filter
 * (`ReviewController.toggle`, one chip at a time).
 */
function sessionOf(manager: WorkspaceManager): WorkspaceSession {
  return (manager as unknown as { session: WorkspaceSession }).session;
}

/** Switch these filter keys off, assigning a new set as every writer must. */
function hide(manager: WorkspaceManager, ...keys: ReviewFilterKey[]): void {
  sessionOf(manager).hiddenReviewStatuses = new Set(keys);
}

/** Select the annotation and press Delete, through the real select tool. */
function pressDelete(seam: SeamContext, id: string): void {
  seam.collection.select(id);
  // The keyboard path reads the selection and the queue only; no Konva needed.
  const handler = selectTool2D.createHandler(seam as unknown as Scene2DContext);
  handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Delete" }));
}

describe("Review decisions — what Save sends", () => {
  it("sends Accept as the status alone", async () => {
    const { manager, backend } = await openWithBoxes(modelBox(REC, "b1"));

    expect(manager.review.accept("b1")).toBe(true);
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
    await manager.flushSave();

    expect(backend.writes).toEqual([
      { op: "update", resource: BBOX_RESOURCE, id: "b1", body: { review_status: "accepted" } },
    ]);
  });

  it("sends Reject as the row's delete, which takes its entity once nothing names it", async () => {
    const { manager, backend } = await openManager(
      { [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1")] } },
      { entities: [entityOf(REC, "ent-b1", { category: "car" })] },
    );
    serveLikeTheApi(backend, REC);

    expect(manager.review.reject("b1")).toBe(true);
    // The row leaves the record at once: no list line, no canvas shape.
    expect(manager.annotations.find("b1")).toBeUndefined();
    expect(rowOf(manager, "b1")).toBeUndefined();
    expect(await manager.flushSave()).toBe(true);

    expect(backend.writes).toEqual([{ op: "delete", resource: BBOX_RESOURCE, id: "b1" }]);
    expect(backend.records[REC][BBOX_RESOURCE]).toEqual([]);
    expect(backend.entities).toEqual([]);
  });

  it("Edit then Accept: the row reads pending until Accept, and one update carries both", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));

    drag(seam, "b1");
    // Unsaved, an edit leaves the row in review: still pending, Accept offered.
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
    expect(rowOf(manager, "b1")?.canAccept).toBe(true);
    expect(manager.review.accept("b1")).toBe(true);
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
    expect(manager.pendingCount).toBe(1);
    await manager.flushSave();

    const updates = updatesSent(backend);
    expect(updates).toHaveLength(1);
    expect(updates[0]).toMatchObject({
      id: "b1",
      body: { coords: MOVED, review_status: "accepted" },
    });
  });

  it("Accept then edit: the update carries the edit and the Accept", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));

    manager.review.accept("b1");
    drag(seam, "b1");
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
    await manager.flushSave();

    const updates = updatesSent(backend);
    expect(updates).toHaveLength(1);
    expect(updates[0]).toMatchObject({
      id: "b1",
      body: { coords: MOVED, review_status: "accepted" },
    });
  });

  it("Edit then Reject: drops the edit and sends the delete only", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));

    drag(seam, "b1");
    manager.review.reject("b1");
    await manager.flushSave();

    expect(backend.writes).toEqual([{ op: "delete", resource: BBOX_RESOURCE, id: "b1" }]);
  });

  it("Reject over an unsaved reassignment drops the entity it queued too", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));

    reassignEntity(
      manager.annotations.find("b1")!,
      { mode: "new", entityFields: { category: "cat" } },
      seam,
    );
    expect(manager.pendingMutations).toHaveLength(2); // the entity create + the update
    manager.review.reject("b1");
    await manager.flushSave();

    // No orphan entity written for a box that was refused.
    expect(backend.writes).toEqual([{ op: "delete", resource: BBOX_RESOURCE, id: "b1" }]);
  });

  it("Reject, then an edit or an Accept: nothing is left to edit or accept", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));

    manager.review.reject("b1");
    drag(seam, "b1");
    expect(manager.review.accept("b1")).toBe(false);
    await manager.flushSave();

    expect(backend.writes).toEqual([{ op: "delete", resource: BBOX_RESOURCE, id: "b1" }]);
  });

  it("Accept then Reject sends the delete only", async () => {
    const { manager, backend } = await openWithBoxes(modelBox(REC, "b1"));

    manager.review.accept("b1");
    manager.review.reject("b1");
    await manager.flushSave();

    expect(backend.writes).toEqual([{ op: "delete", resource: BBOX_RESOURCE, id: "b1" }]);
  });

  it("Accept twice sends one acceptance", async () => {
    const { manager, backend } = await openWithBoxes(modelBox(REC, "b1"));

    expect(manager.review.accept("b1")).toBe(true);
    expect(manager.review.accept("b1")).toBe(false);
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
    await manager.flushSave();

    expect(backend.writes).toEqual([
      { op: "update", resource: BBOX_RESOURCE, id: "b1", body: { review_status: "accepted" } },
    ]);
  });

  it("Discard undoes every decision: an Accept, and a Reject, whose row comes back", async () => {
    const { manager, backend } = await openWithBoxes(modelBox(REC, "b1"), modelBox(REC, "b2"));

    manager.review.accept("b1");
    manager.review.reject("b2");
    await manager.discardChanges();
    await manager.flushSave();

    expect(manager.pendingCount).toBe(0);
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
    expect(statusOf(manager, "b2")).toBe(REVIEW_STATUS.PENDING);
    expect(backend.writes).toEqual([]);
  });

  it("offers no Accept on a row stored accepted, but still its Reject", async () => {
    const { manager, backend } = await openWithBoxes(modelBox(REC, "b1", "accepted"));

    expect(rowOf(manager, "b1")).toMatchObject({ canAccept: false, canReject: true });
    expect(manager.review.accept("b1")).toBe(false);
    expect(manager.pendingCount).toBe(0);
    // Rejecting an accepted row is allowed: it deletes it.
    expect(manager.review.reject("b1")).toBe(true);
    await manager.flushSave();

    expect(backend.writes).toEqual([{ op: "delete", resource: BBOX_RESOURCE, id: "b1" }]);
  });

  it("takes no decision on a person's annotation", async () => {
    const { manager } = await openWithBoxes(humanBox(REC, "h1"));

    expect(manager.review.accept("h1")).toBe(false);
    expect(manager.review.reject("h1")).toBe(false);
    expect(manager.pendingCount).toBe(0);
  });

  it("decides on another kind through the same path (a model's mask)", async () => {
    const { manager, backend } = await openManager({
      [REC]: { [MASK_RESOURCE]: [modelMask(REC, "m1")] },
    });

    manager.review.accept("m1");
    await manager.flushSave();

    expect(backend.writes).toEqual([
      { op: "update", resource: MASK_RESOURCE, id: "m1", body: { review_status: "accepted" } },
    ]);
  });
});

describe("Review status on what a widget displays", () => {
  it("re-runs a widget's display when the filter changes", async () => {
    const { manager, seam } = await openWithBoxes(
      modelBox(REC, "b1"),
      modelBox(REC, "b2", "accepted"),
      humanBox(REC, "h1"),
    );
    const displayed: string[][] = [];
    const stop = $effect.root(() => {
      $effect(() => {
        displayed.push(seam.collection.items.map((a) => a.id));
      });
    });
    flushSync();
    // Nothing is hidden by default.
    expect(displayed.at(-1)).toEqual(["b1", "b2", "h1"]);

    hide(manager, REVIEW_STATUS.ACCEPTED);
    flushSync();
    expect(displayed.at(-1)).toEqual(["b1", "h1"]);

    hide(manager, REVIEW_STATUS.PENDING, HUMAN_REVIEW_FILTER);
    flushSync();
    expect(displayed.at(-1)).toEqual(["b2"]);

    hide(manager);
    flushSync();
    expect(displayed.at(-1)).toEqual(["b1", "b2", "h1"]);

    stop();
  });

  it("always shows a draft, whatever is hidden", async () => {
    const { manager, seam } = await openWithBoxes(humanBox(REC, "h1"));
    hide(manager, HUMAN_REVIEW_FILTER);

    seam.collection.add({
      id: "draft",
      entityId: "ent-draft",
      kind: "bbox",
      viewId: viewIdOf(REC),
      geometry: [0.5, 0.5, 0.1, 0.1],
      persisted: false,
    });

    expect(seam.collection.items.map((a) => a.id)).toEqual(["draft"]);
  });

  it("still saves an edit of a row the filter hides", async () => {
    const { manager, seam, backend } = await openWithBoxes(modelBox(REC, "b1"));

    hide(manager, REVIEW_STATUS.PENDING);
    expect(seam.collection.items).toEqual([]);
    drag(seam, "b1");
    await manager.flushSave();

    expect(updatesSent(backend).map((w) => w.id)).toEqual(["b1"]);
  });

  it("keeps the filter when another record opens", async () => {
    const other = "rec-2";
    const { manager } = await openManager({
      [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1", "accepted")] },
      [other]: {
        [BBOX_RESOURCE]: [modelBox(other, "b2"), modelBox(other, "b3", "accepted")],
      },
    });
    hide(manager, REVIEW_STATUS.ACCEPTED);

    await manager.openRecord(DATASET_ID, other, VIEWPORT);

    expect([...sessionOf(manager).hiddenReviewStatuses]).toEqual([REVIEW_STATUS.ACCEPTED]);
    expect(widgetSeam(manager).collection.items.map((a) => a.id)).toEqual(["b2"]);
  });

  it("re-runs a widget's display when a chip is toggled or a decision is taken", async () => {
    const { manager, seam } = await openWithBoxes(
      modelBox(REC, "b1"),
      modelBox(REC, "b2", "accepted"),
    );
    const displayed: string[][] = [];
    const stop = $effect.root(() => {
      $effect(() => {
        displayed.push(seam.collection.items.map((a) => a.id));
      });
    });
    flushSync();
    // No chip is off by default.
    expect(displayed.at(-1)).toEqual(["b1", "b2"]);

    manager.review.toggle(REVIEW_STATUS.ACCEPTED);
    flushSync();
    expect(displayed.at(-1)).toEqual(["b1"]);

    manager.review.accept("b1");
    flushSync();
    expect(displayed.at(-1)).toEqual([]);

    manager.review.toggle(REVIEW_STATUS.ACCEPTED);
    manager.review.reject("b2");
    flushSync();
    expect(displayed.at(-1)).toEqual(["b1"]);

    stop();
  });

  it("drops a selection the filter has just hidden", async () => {
    const { manager } = await openWithBoxes(modelBox(REC, "b1"));
    manager.annotations.select("b1");

    manager.review.toggle(REVIEW_STATUS.PENDING);

    expect(manager.annotations.selectedId).toBeNull();
  });
});

describe("An edit leaves the row in review until it is saved", () => {
  it("an edit reads pending, keeps Accept, and Save stores it accepted", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    serveLikeTheApi(backend, REC);

    drag(seam, "b1");
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
    expect(rowOf(manager, "b1")).toMatchObject({ canAccept: true, canReject: true });
    expect(await manager.flushSave()).toBe(true);

    // Saving the edit is the person's choice to keep the row: the server stores it accepted,
    // keeping the model's provenance and score.
    expect(backend.records[REC][BBOX_RESOURCE][0]).toMatchObject({
      coords: MOVED,
      review_status: "accepted",
      source_type: "model",
      confidence: 0.87,
    });
    // The row reads so, and is not offered Accept.
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
    expect(rowOf(manager, "b1")?.canAccept).toBe(false);
    expect(manager.review.accept("b1")).toBe(false);
  });

  it("moving a model's box to another entity reads pending until saved", async () => {
    const { manager, backend } = await openManager(
      { [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1")] } },
      { entities: [entityOf(REC, "ent-b1"), entityOf(REC, "ent-x")] },
    );
    serveLikeTheApi(backend, REC);

    reassignEntity(
      manager.annotations.find("b1")!,
      { mode: "existing", entityId: "ent-x" },
      widgetSeam(manager),
    );

    // Unsaved, the reassignment leaves the row in review; saved, it reads accepted.
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
    expect(rowOf(manager, "b1")?.canAccept).toBe(true);
    await manager.flushSave();
    const updates = updatesSent(backend);
    expect(updates).toHaveLength(1);
    expect(updates[0]).toMatchObject({ id: "b1", body: { entity_id: "ent-x" } });
    expect(updates[0].op === "update" && updates[0].body).not.toHaveProperty("review_status");
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
  });

  it("Accept then edit: stays accepted, and one update carries both", async () => {
    const { manager, seam } = await openWithBoxes(modelBox(REC, "b1"));

    manager.review.accept("b1");
    drag(seam, "b1");

    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
    expect(rowOf(manager, "b1")).toMatchObject({ canAccept: false, canReject: true });
    expect(manager.pendingMutations).toHaveLength(1);
    expect(manager.pendingMutations[0]).toMatchObject({
      op: "update",
      id: "b1",
      body: { coords: MOVED, review_status: "accepted" },
    });
  });

  it("an edit saved reads accepted before any read-back, and is not offered Accept", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    const read = deferred();
    backend.holdListings = read.promise;

    drag(seam, "b1");
    backend.log.length = 0;
    const saving = manager.flushSave();
    // The write has landed; the rows read back are still on their way.
    await vi.waitFor(() => expect(backend.log).toContain(`list ${BBOX_RESOURCE}`));

    // The server stores the moved box accepted; the row knows it without a read.
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
    expect(rowOf(manager, "b1")?.canAccept).toBe(false);
    expect(manager.review.accept("b1")).toBe(false);
    read.resolve();
    await saving;
  });

  it("a save that fails leaves the stored status as it was", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    backend.failWrites = new Error("backend down");

    drag(seam, "b1");
    expect(await manager.flushSave()).toBe(false);
    expect(manager.annotations.find("b1")?.review?.storedStatus).toBe(REVIEW_STATUS.PENDING);
    // The edit is unsaved again: the row reads pending, and can be accepted.
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
    expect(rowOf(manager, "b1")?.canAccept).toBe(true);
    // Still stored pending once the failed edit is thrown away, too.
    backend.failWrites = undefined;
    await manager.discardChanges();
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
    expect(manager.review.accept("b1")).toBe(true);
  });
});

describe("An edit that leaves the content as stored is not an edit", () => {
  it("a box dragged away and back queues nothing, and reads its stored status", async () => {
    const { manager, seam } = await openWithBoxes(modelBox(REC, "b1"));

    drag(seam, "b1");
    drag(seam, "b1", STORED);

    expect(manager.pendingCount).toBe(0);
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
  });

  it("Accept, then a box dragged away and back: the Accept alone stays queued", async () => {
    const { manager, seam } = await openWithBoxes(modelBox(REC, "b1"));

    manager.review.accept("b1");
    drag(seam, "b1");
    drag(seam, "b1", STORED);

    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
    expect(manager.pendingMutations).toEqual([
      expect.objectContaining({ op: "update", id: "b1", body: { review_status: "accepted" } }),
    ]);
  });

  it("a difference below what storage keeps is no difference", async () => {
    const { manager, seam } = await openWithBoxes(modelBox(REC, "b1"));
    // What a float32 round trip leaves of the stored values.
    const roundTripped: BBoxGeometry = [0.1 + 1e-9, 0.1 - 1e-9, 0.2, 0.2 + 1e-9];

    drag(seam, "b1", roundTripped);

    expect(manager.pendingCount).toBe(0);
  });

  it("a box dragged back to where its last save left it queues nothing", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    serveLikeTheApi(backend, REC);

    drag(seam, "b1");
    await manager.flushSave();
    drag(seam, "b1", STORED);
    drag(seam, "b1", MOVED);

    expect(manager.pendingCount).toBe(0);
  });

  it("re-picking the entity a box has queues nothing", async () => {
    const { manager } = await openManager(
      { [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1")] } },
      { entities: [entityOf(REC, "ent-b1", { category: "dog" })] },
    );
    const seam = widgetSeam(manager);

    reassignEntity(manager.annotations.find("b1")!, { mode: "existing", entityId: "ent-b1" }, seam);

    expect(manager.pendingCount).toBe(0);
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
  });

  it("re-picking the entity a box has, then Accept, sends the acceptance", async () => {
    const { manager, backend } = await openManager(
      { [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1")] } },
      { entities: [entityOf(REC, "ent-b1", { category: "dog" })] },
    );
    const seam = widgetSeam(manager);

    reassignEntity(manager.annotations.find("b1")!, { mode: "existing", entityId: "ent-b1" }, seam);
    expect(manager.pendingCount).toBe(0);
    expect(manager.review.accept("b1")).toBe(true);
    await manager.flushSave();

    expect(backend.writes).toEqual([
      { op: "update", resource: BBOX_RESOURCE, id: "b1", body: { review_status: "accepted" } },
    ]);
  });

  it("Accept, then re-picking the same entity, keeps the acceptance", async () => {
    const { manager, backend } = await openManager(
      { [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1")] } },
      { entities: [entityOf(REC, "ent-b1", { category: "dog" })] },
    );
    const seam = widgetSeam(manager);

    manager.review.accept("b1");
    reassignEntity(manager.annotations.find("b1")!, { mode: "existing", entityId: "ent-b1" }, seam);
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
    await manager.flushSave();

    expect(backend.writes).toEqual([
      { op: "update", resource: BBOX_RESOURCE, id: "b1", body: { review_status: "accepted" } },
    ]);
  });

  it("a 3D box saved from its HUD turned less than storage can tell queues nothing", async () => {
    const box3d: Row = {
      ...modelBox(REC, "box-1"),
      view_id: "",
      coords: [0, 0, 0, 1, 1, 1],
      format: "xyzwhd",
      rotation: [1, 0, 0, 0, 1, 0, 0, 0, 1],
    };
    const { manager } = await openManager({ [REC]: { [BBOX3D_RESOURCE]: [box3d] } });
    const session = new BBox3DSession(widgetSeam(manager, "point-cloud-widget"));
    session.setResetEditor(() => {});
    // A turn a hair away from the stored one, closer than float32 storage tells
    // apart: the edit rule's tolerance, not the HUD's own untouched check — a
    // box the real editor opens and saves untouched is in bbox3dSession.test.ts.
    const barelyTurned: Rotation3x3 = [1 - 1e-8, 1e-9, 0, -1e-9, 1 - 1e-8, 0, 0, 0, 1];

    session.reportReady([0, 0, 0, 1, 1, 1], barelyTurned, "box-1");
    session.save();

    expect(manager.pendingCount).toBe(0);
    expect(statusOf(manager, "box-1")).toBe(REVIEW_STATUS.PENDING);
  });

  it("a model's classification moved onto the entity it has keeps its score and status", async () => {
    const classification: Row = {
      id: "c1",
      record_id: REC,
      entity_id: "ent-cat",
      view_id: viewIdOf(REC),
      labels: ["cat"],
      confidences: [0.87],
      source_type: "model",
      source_name: "classification",
      source_metadata: MODEL_METADATA,
      review_status: "pending",
    };
    const { manager } = await openManager(
      { [REC]: { [CLASSIFICATION_RESOURCE]: [classification] } },
      { entities: [entityOf(REC, "ent-cat", { category: "cat" })] },
    );
    const seam = widgetSeam(manager);
    // The model's score is read from its per-label list.
    expect(rowOf(manager, "c1")?.confidence).toBe(0.87);

    beginEntityReassign(manager.annotations.find("c1")!, seam, { label: "classification" });
    manager.confirmPendingAnnotation({ mode: "existing", entityId: "ent-cat" });

    // The interface rewrites the score as a person's, but the score is the
    // model's: the server ignores it, so nothing changed and nothing is sent.
    expect(manager.pendingCount).toBe(0);
    expect(statusOf(manager, "c1")).toBe(REVIEW_STATUS.PENDING);
  });
});

describe("Delete on a model's annotation is its reject", () => {
  it("queues the delete and removes the row", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));

    pressDelete(seam, "b1");

    expect(manager.annotations.find("b1")).toBeUndefined();
    expect(seam.collection.items.map((a) => a.id)).toEqual([]);
    // The gesture consumes the selection, as a delete does.
    expect(manager.annotations.selectedId).toBeNull();
    await manager.flushSave();

    expect(backend.writes).toEqual([{ op: "delete", resource: BBOX_RESOURCE, id: "b1" }]);
  });

  it("rejects an accepted annotation too", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1", "accepted"));

    pressDelete(seam, "b1");
    expect(manager.annotations.find("b1")).toBeUndefined();
    await manager.flushSave();

    expect(backend.writes).toEqual([{ op: "delete", resource: BBOX_RESOURCE, id: "b1" }]);
  });

  it("deletes a person's annotation, as before", async () => {
    const { manager, backend, seam } = await openWithBoxes(humanBox(REC, "h1"));

    pressDelete(seam, "h1");
    expect(manager.annotations.find("h1")).toBeUndefined();
    await manager.flushSave();

    expect(backend.writes).toEqual([{ op: "delete", resource: BBOX_RESOURCE, id: "h1" }]);
  });

  it("drops a model's unsaved edit before the delete, and sends the delete only", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));

    drag(seam, "b1");
    pressDelete(seam, "b1");
    expect(manager.pendingMutations.map((m) => m.op)).toEqual(["delete"]);
    await manager.flushSave();

    expect(backend.writes).toEqual([{ op: "delete", resource: BBOX_RESOURCE, id: "b1" }]);
  });

  it("drops the entity an unsaved reassignment queued for a model's row", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));

    reassignEntity(
      manager.annotations.find("b1")!,
      { mode: "new", entityFields: { category: "cat" } },
      seam,
    );
    expect(manager.pendingMutations).toHaveLength(2); // the entity create + the update
    pressDelete(seam, "b1");
    await manager.flushSave();

    // No orphan entity written for a box that was rejected.
    expect(backend.writes).toEqual([{ op: "delete", resource: BBOX_RESOURCE, id: "b1" }]);
  });

  it("drops a person's unsaved edit before the delete, as for a model's row", async () => {
    const { manager, backend, seam } = await openWithBoxes(humanBox(REC, "h1"));

    // Moved, then onto a new entity, then deleted: neither the edit nor the
    // entity made for it is sent, so no entity is left that nothing names.
    drag(seam, "h1");
    reassignEntity(
      manager.annotations.find("h1")!,
      { mode: "new", entityFields: { category: "cat" } },
      seam,
    );
    pressDelete(seam, "h1");
    await manager.flushSave();

    expect(backend.writes).toEqual([{ op: "delete", resource: BBOX_RESOURCE, id: "h1" }]);
  });

  it("drops its own row's work only", async () => {
    const { manager, backend, seam } = await openWithBoxes(
      modelBox(REC, "b1"),
      modelBox(REC, "b2"),
    );

    drag(seam, "b1");
    drag(seam, "b2");
    pressDelete(seam, "b1");
    await manager.flushSave();

    expect(backend.writes).toContainEqual({ op: "delete", resource: BBOX_RESOURCE, id: "b1" });
    const updates = updatesSent(backend);
    expect(updates.filter((w) => w.op === "update" && w.id === "b1")).toEqual([]);
    expect(updates.find((w) => w.op === "update" && w.id === "b2")).toMatchObject({
      body: { coords: MOVED },
    });
  });

  it("rejects from the 3D box HUD as well, the same single path", async () => {
    const box3d: Row = {
      ...modelBox(REC, "box-1"),
      view_id: "",
      coords: [0, 0, 0, 1, 1, 1],
      format: "xyzwhd",
      rotation: [1, 0, 0, 0, 1, 0, 0, 0, 1],
    };
    const { manager, backend } = await openManager({ [REC]: { [BBOX3D_RESOURCE]: [box3d] } });
    const session = new BBox3DSession(widgetSeam(manager, "point-cloud-widget"));
    session.setResetEditor(() => {});
    const identity: Rotation3x3 = [1, 0, 0, 0, 1, 0, 0, 0, 1];

    session.reportReady([0, 0, 0, 1, 1, 1], identity, "box-1");
    expect(session.editingDeleteGesture).toBe("reject");
    session.deleteBox();
    expect(manager.annotations.find("box-1")).toBeUndefined();
    await manager.flushSave();

    expect(backend.writes).toEqual([{ op: "delete", resource: BBOX3D_RESOURCE, id: "box-1" }]);
  });

  it("names what the gesture will do, for the controls to say it", async () => {
    const { manager } = await openWithBoxes(
      modelBox(REC, "pending"),
      modelBox(REC, "accepted", "accepted"),
      humanBox(REC, "human"),
    );
    const draft: LocalAnnotation = {
      id: "draft",
      entityId: "",
      kind: "bbox",
      viewId: viewIdOf(REC),
      geometry: MOVED,
      persisted: false,
    };

    const queue = widgetSeam(manager).mutations;
    expect(deleteGestureFor(manager.annotations.find("pending")!, queue)).toBe("reject");
    expect(deleteGestureFor(manager.annotations.find("accepted")!, queue)).toBe("reject");
    expect(deleteGestureFor(manager.annotations.find("human")!, queue)).toBe("delete");
    expect(deleteGestureFor(draft, queue)).toBe("delete");
    // While "Save & next" runs, a model's annotation is neither rejected nor deleted.
    expect(deleteGestureFor(manager.annotations.find("pending")!, { decisionsLocked: true })).toBe(
      "locked",
    );
    expect(deleteGestureFor(manager.annotations.find("human")!, { decisionsLocked: true })).toBe(
      "delete",
    );
  });

  it("cancels no gesture when it does nothing", async () => {
    const { manager, seam } = await openWithBoxes(modelBox(REC, "b1"));
    let cancelled = 0;
    const cancel = () => cancelled++;

    // "Save & next" runs: the reject is held back.
    deleteLocalAnnotation(
      manager.annotations.find("b1")!,
      seam.collection,
      { ...seam.mutations, decisionsLocked: true },
      "w",
      cancel,
    );

    expect(cancelled).toBe(0);
    expect(manager.annotations.find("b1")).toBeDefined();
    expect(manager.pendingCount).toBe(0);
  });

  it("is undone only by Discard, which brings the row back with the rest of the record's unsaved work", async () => {
    const { manager, backend, seam } = await openWithBoxes(
      modelBox(REC, "b1"),
      modelBox(REC, "b2"),
    );

    drag(seam, "b2");
    pressDelete(seam, "b1");
    await manager.discardChanges();
    await manager.flushSave();

    expect(manager.pendingCount).toBe(0);
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
    // The edit of the other row went with it.
    expect(geometryOf(manager, "b2")).toEqual(STORED);
    expect(backend.writes).toEqual([]);
  });
});

describe("Decisions scoped to their own row", () => {
  it("an unsaved edit of another row does not stand in an Accept's way", async () => {
    const { manager, backend, seam } = await openWithBoxes(
      modelBox(REC, "b1"),
      modelBox(REC, "b2"),
    );

    drag(seam, "b2");
    expect(manager.review.accept("b1")).toBe(true);
    await manager.flushSave();

    const updates = updatesSent(backend);
    expect(updates).toContainEqual({
      op: "update",
      resource: BBOX_RESOURCE,
      id: "b1",
      body: { review_status: "accepted" },
    });
    expect(updates.find((w) => w.op === "update" && w.id === "b2")).toMatchObject({
      body: { coords: MOVED },
    });
  });
});
