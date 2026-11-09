/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { flushSync } from "svelte";
import { describe, expect, it, vi } from "vitest";

import { REVIEW_PANEL_SOURCE_ID } from "../reviewController.svelte.js";
import type { NextRecordToReview } from "../reviewGateway.js";
import type { WorkspaceManager } from "../workspaceManager.svelte.js";
import {
  DATASET_ID,
  deferred,
  entityOf,
  humanBox,
  modelBox,
  openManager,
  viewIdOf,
  VIEWPORT,
  widgetSeam,
} from "./workspaceHarness.js";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import { BBOX3D_RESOURCE } from "$lib/annotations/kinds/3d/bbox3d/bbox3dPayloadBuilder.js";
import { BBox3DSession } from "$lib/annotations/kinds/3d/bbox3d/bbox3dSession.svelte.js";
import {
  beginEntityReassign,
  commitGeometryEdit,
  commitNewAnnotation,
  deleteGestureFor,
  deleteLocalAnnotation,
  reassignEntity,
} from "$lib/annotations/payloadBuilders.js";
import { HUMAN_REVIEW_FILTER, REVIEW_STATUS } from "$lib/annotations/reviewStatus.js";
import type { Scene2DContext, SeamContext } from "$lib/annotations/scene/sceneContext.js";
import { selectTool2D } from "$lib/annotations/scene/selectTool2D.js";
import type { Rotation3x3 } from "$lib/annotations/types.js";

// The review controller through the real manager: its decisions reach the real
// queue, "Save & next" saves through the real flush and opens the next record
// through the real loader. Only the HTTP edge is fake, and it records.

const REC_1 = "rec-1";
const REC_2 = "rec-2";
const REC_3 = "rec-3";

function twoRecords() {
  return {
    [REC_1]: { [BBOX_RESOURCE]: [modelBox(REC_1, "b1"), humanBox(REC_1, "h1")] },
    [REC_2]: { [BBOX_RESOURCE]: [modelBox(REC_2, "b2")] },
  };
}

/** Select the annotation and press Delete in an image widget, through the real select tool. */
function pressDelete(seam: SeamContext, id: string): void {
  seam.collection.select(id);
  const handler = selectTool2D.createHandler(seam as unknown as Scene2DContext);
  handler.onKeyDown?.(new KeyboardEvent("keydown", { key: "Delete" }));
}

/**
 * Start "Save & next" and wait until it is asking the server for the next
 * record. Its run comes back wrapped: awaiting a bare promise here would wait
 * for the whole run, which waits for the lookup the test still holds.
 */
async function saveAndNextUpToTheLookup(manager: WorkspaceManager, log: string[]) {
  const moving = manager.review.saveAndNext(VIEWPORT);
  await vi.waitFor(() => expect(log).toContain("nextRecordToReview"));
  return { moving };
}

describe("ReviewController — Save & next", () => {
  it("saves first, then opens the next record the server names", async () => {
    const { manager, backend, reviewGateway } = await openManager(twoRecords(), {
      next: { recordId: REC_2, remaining: 2 },
    });
    manager.review.accept("b1");
    backend.log.length = 0;

    await manager.review.saveAndNext();

    // The decision reached the backend before the next record was asked for.
    expect(backend.log.indexOf(`update ${BBOX_RESOURCE}`)).toBeLessThan(
      backend.log.indexOf("nextRecordToReview"),
    );
    expect(reviewGateway.asked).toEqual([
      { datasetId: DATASET_ID, status: REVIEW_STATUS.PENDING, after: REC_1 },
    ]);
    expect(manager.recordId).toBe(REC_2);
    expect(manager.annotations.find("b2")).toBeDefined();
    expect(manager.review.outcome).toEqual({
      kind: "opened",
      recordId: REC_2,
      status: REVIEW_STATUS.PENDING,
      remaining: 2,
    });
  });

  it("stays on the record, decision still queued, when the save fails", async () => {
    const { manager, backend, reviewGateway } = await openManager(twoRecords(), {
      next: { recordId: REC_2, remaining: 1 },
    });
    backend.failWrites = new Error("backend down");
    manager.review.accept("b1");

    await manager.review.saveAndNext();

    expect(reviewGateway.asked).toEqual([]);
    expect(manager.recordId).toBe(REC_1);
    expect(manager.pendingCount).toBe(1);
    expect(manager.review.outcome).toEqual({ kind: "not-saved", saveFailed: true });
  });

  it("says nothing is left, and reopens nothing, when no record holds the status", async () => {
    const { manager, backend } = await openManager(twoRecords(), {
      next: { recordId: null, remaining: 0 },
    });
    backend.log.length = 0;

    await manager.review.saveAndNext();

    expect(backend.log).not.toContain("getDataset");
    expect(manager.recordId).toBe(REC_1);
    expect(manager.review.outcome).toEqual({ kind: "none-left", status: REVIEW_STATUS.PENDING });
  });

  it("does not reopen the record it is on when the server wraps round to it", async () => {
    const { manager, backend } = await openManager(twoRecords(), {
      next: { recordId: REC_1, remaining: 1 },
    });
    backend.log.length = 0;

    await manager.review.saveAndNext();

    expect(backend.log).not.toContain("getDataset");
    expect(manager.review.outcome).toEqual({ kind: "none-left", status: REVIEW_STATUS.PENDING });
  });

  it("looks for the status the reviewer chose", async () => {
    const { manager, reviewGateway } = await openManager(twoRecords(), {
      next: { recordId: REC_2, remaining: 1 },
    });

    manager.review.setNextStatus(REVIEW_STATUS.ACCEPTED);
    manager.review.setNextStatus("not-a-status");
    await manager.review.saveAndNext();

    expect(reviewGateway.asked[0]).toMatchObject({ status: REVIEW_STATUS.ACCEPTED, after: REC_1 });
  });

  it("reports a failed lookup without moving", async () => {
    const { manager } = await openManager(twoRecords(), { next: new Error("network down") });

    await manager.review.saveAndNext();

    expect(manager.recordId).toBe(REC_1);
    expect(manager.review.outcome).toEqual({ kind: "failed", message: "network down" });
    expect(manager.review.navigating).toBe(false);
  });

  it("forgets its message once another record is opened from the list", async () => {
    const { manager } = await openManager(twoRecords(), {
      next: { recordId: null, remaining: 0 },
    });
    await manager.review.saveAndNext();
    expect(manager.review.outcome?.kind).toBe("none-left");

    await manager.openRecord(DATASET_ID, REC_2);

    expect(manager.review.outcome).toBeNull();
  });

  it("does not read the annotations back when there was nothing to save", async () => {
    const { manager, backend } = await openManager(twoRecords(), {
      next: { recordId: null, remaining: 0 },
    });
    backend.log.length = 0;

    await manager.review.saveAndNext();

    expect(backend.log.filter((call) => call.startsWith("list "))).toEqual([]);
  });

  it("stays, edit kept, when an edit was made while it looked for the next record", async () => {
    const lookup = deferred<NextRecordToReview>();
    const { manager, backend } = await openManager(
      {
        [REC_1]: { [BBOX_RESOURCE]: [modelBox(REC_1, "b1"), modelBox(REC_1, "b3")] },
        [REC_2]: { [BBOX_RESOURCE]: [modelBox(REC_2, "b2")] },
      },
      { next: lookup.promise },
    );
    manager.review.accept("b1");

    const { moving } = await saveAndNextUpToTheLookup(manager, backend.log);
    commitGeometryEdit(widgetSeam(manager), "b3", [0.3, 0.3, 0.2, 0.2]);
    lookup.resolve({ recordId: REC_2, remaining: 1 });
    await moving;

    expect(manager.recordId).toBe(REC_1);
    expect(manager.pendingCount).toBe(1);
    expect(manager.review.outcome).toEqual({ kind: "not-saved" });
  });

  it("takes no decision while it runs, whatever the path, and says so", async () => {
    const lookup = deferred<NextRecordToReview>();
    const box3d = {
      ...modelBox(REC_1, "box-1"),
      view_id: "",
      coords: [0, 0, 0, 1, 1, 1],
      format: "xyzwhd",
      rotation: [1, 0, 0, 0, 1, 0, 0, 0, 1],
    };
    const { manager, backend } = await openManager(
      {
        [REC_1]: {
          [BBOX_RESOURCE]: [modelBox(REC_1, "b1"), modelBox(REC_1, "b3")],
          [BBOX3D_RESOURCE]: [box3d],
        },
        [REC_2]: { [BBOX_RESOURCE]: [modelBox(REC_2, "b2")] },
      },
      { next: lookup.promise },
    );
    const image = widgetSeam(manager);
    const pointCloud = widgetSeam(manager, "point-cloud-widget");
    const hud = new BBox3DSession(pointCloud);
    hud.setResetEditor(() => {});
    const identity: Rotation3x3 = [1, 0, 0, 0, 1, 0, 0, 0, 1];

    const { moving } = await saveAndNextUpToTheLookup(manager, backend.log);
    // The Review tab, the Delete key, the image's trash button, the 3D HUD.
    expect(manager.review.reject("b1")).toBe(false);
    pressDelete(image, "b3");
    deleteLocalAnnotation(
      manager.annotations.find("b1")!,
      image.collection,
      image.mutations,
      "image-widget",
    );
    hud.reportReady([0, 0, 0, 1, 1, 1], identity, "box-1");
    hud.deleteBox();
    // What each control says before it is pressed.
    expect(deleteGestureFor(manager.annotations.find("b3")!, image.mutations)).toBe("locked");

    expect(manager.pendingCount).toBe(0);
    for (const id of ["b1", "b3", "box-1"]) {
      expect(manager.annotations.find(id)?.review?.status).toBe(REVIEW_STATUS.PENDING);
    }
    lookup.resolve({ recordId: null, remaining: 0 });
    await moving;

    // Once it is over, the Delete key rejects again: it deletes the box.
    expect(deleteGestureFor(manager.annotations.find("b3")!, image.mutations)).toBe("reject");
    pressDelete(image, "b3");
    expect(manager.annotations.find("b3")).toBeUndefined();
    expect(manager.pendingMutations).toEqual([
      expect.objectContaining({ op: "delete", resource: BBOX_RESOURCE, id: "b3" }),
    ]);
  });

  it("offers no decision while it runs", async () => {
    const lookup = deferred<NextRecordToReview>();
    const { manager, backend } = await openManager(twoRecords(), { next: lookup.promise });

    const { moving } = await saveAndNextUpToTheLookup(manager, backend.log);
    expect(manager.review.rows.find((r) => r.id === "b1")).toMatchObject({
      canAccept: false,
      acceptRefusal: "busy",
      canReject: false,
      rejectRefusal: "busy",
    });
    expect(manager.review.accept("b1")).toBe(false);
    lookup.resolve({ recordId: null, remaining: 0 });
    await moving;

    expect(manager.review.rows.find((r) => r.id === "b1")?.canAccept).toBe(true);
  });

  it("leaves the reviewer on a record they opened from the list meanwhile", async () => {
    const lookup = deferred<NextRecordToReview>();
    const { manager, backend } = await openManager(
      { ...twoRecords(), [REC_3]: { [BBOX_RESOURCE]: [modelBox(REC_3, "b3")] } },
      { next: lookup.promise },
    );

    const { moving } = await saveAndNextUpToTheLookup(manager, backend.log);
    // Nothing unsaved on it: only the choice of record is at stake.
    await manager.openRecord(DATASET_ID, REC_3, VIEWPORT);
    lookup.resolve({ recordId: REC_2, remaining: 1 });
    await moving;

    expect(manager.recordId).toBe(REC_3);
    // No word about a move that did not happen.
    expect(manager.review.outcome).toBeNull();
  });

  it("moves on once a failed draft has been deleted", async () => {
    const { manager, backend } = await openManager(twoRecords(), {
      next: { recordId: REC_2, remaining: 1 },
    });
    const draft = commitNewAnnotation(widgetSeam(manager), "bbox", [0, 0, 0.1, 0.1]);
    backend.failWrites = new Error("backend down");
    expect(await manager.flushSave()).toBe(false);
    backend.failWrites = undefined;

    // What failed is gone with the draft: there is no failure left to stop on.
    manager.deleteAnnotation(manager.annotations.find(draft.id)!, "image-widget");
    await manager.review.saveAndNext(VIEWPORT);

    expect(manager.recordId).toBe(REC_2);
  });

  it("stays while a widget holds a staged edit, and moves once it is let go", async () => {
    const { manager } = await openManager(twoRecords(), {
      next: { recordId: REC_2, remaining: 1 },
    });
    const flag = widgetSeam(manager, "point-cloud-widget").claimStagedWork!(() => {});

    flag.set(true);
    await manager.review.saveAndNext(VIEWPORT);
    expect(manager.recordId).toBe(REC_1);
    expect(manager.review.outcome).toEqual({ kind: "not-saved" });

    flag.set(false);
    await manager.review.saveAndNext(VIEWPORT);
    expect(manager.recordId).toBe(REC_2);
  });

  it("stays while an entity is being chosen for a saved box, and the choice still applies", async () => {
    const { manager, backend } = await openManager(twoRecords(), {
      next: { recordId: REC_2, remaining: 1 },
      entities: [entityOf(REC_1, "ent-b1"), entityOf(REC_1, "ent-x")],
    });
    manager.review.accept("b1");
    // The entity form of a reassignment: no draft, every row is saved.
    beginEntityReassign(manager.annotations.find("b1")!, widgetSeam(manager), {
      label: "box entity",
    });
    backend.log.length = 0;

    expect(await manager.flushSave()).toBe(false);
    // The save read the record back around the open form.
    expect(backend.log).toContain(`list ${BBOX_RESOURCE}`);
    await manager.review.saveAndNext(VIEWPORT);
    expect(manager.recordId).toBe(REC_1);
    expect(manager.review.outcome).toEqual({ kind: "not-saved" });

    manager.confirmPendingAnnotation({ mode: "existing", entityId: "ent-x" });
    expect(manager.annotations.find("b1")?.entityId).toBe("ent-x");
    expect(
      manager.pendingMutations.map((m) => m.op === "update" && [m.id, m.body.entity_id]),
    ).toEqual([["b1", "ent-x"]]);
  });

  it("keeps the reviewer's status filter on the next record", async () => {
    const { manager } = await openManager(twoRecords(), {
      next: { recordId: REC_2, remaining: 1 },
    });
    manager.review.toggle(HUMAN_REVIEW_FILTER);
    manager.review.toggle(REVIEW_STATUS.ACCEPTED);

    await manager.review.saveAndNext();

    expect(manager.recordId).toBe(REC_2);
    expect(manager.review.isHidden(HUMAN_REVIEW_FILTER)).toBe(true);
    expect(manager.review.isHidden(REVIEW_STATUS.ACCEPTED)).toBe(true);
    expect(manager.review.isHidden(REVIEW_STATUS.PENDING)).toBe(false);
  });
});

describe("ReviewController — what 'Not moved' says, and for how long", () => {
  /** Save & next on record 1, refused by a failing save; the backend back since. */
  async function notMovedByAFailedSave() {
    const opened = await openManager(
      {
        [REC_1]: { [BBOX_RESOURCE]: [modelBox(REC_1, "b1"), modelBox(REC_1, "b3")] },
        [REC_2]: { [BBOX_RESOURCE]: [modelBox(REC_2, "b2")] },
      },
      { next: { recordId: REC_2, remaining: 1 } },
    );
    opened.manager.review.accept("b1");
    opened.backend.failWrites = new Error("backend down");
    await opened.manager.review.saveAndNext(VIEWPORT);
    opened.backend.failWrites = undefined;
    expect(opened.manager.review.outcome).toEqual({ kind: "not-saved", saveFailed: true });
    return opened;
  }

  /** Save & next on record 1, refused by work a widget holds staged. */
  async function notMovedByStagedWork() {
    const opened = await openManager(twoRecords(), { next: { recordId: REC_2, remaining: 1 } });
    const flag = widgetSeam(opened.manager).claimStagedWork!(() => {});
    flag.set(true);
    await opened.manager.review.saveAndNext(VIEWPORT);
    expect(opened.manager.review.outcome).toEqual({ kind: "not-saved" });
    return { ...opened, flag };
  }

  it("is gone for good after Discard: a decision taken at once does not bring it back", async () => {
    const { manager } = await notMovedByAFailedSave();

    const discarding = manager.review.discard();
    // Taken while Discard reads the record back, before anything else ran.
    expect(manager.review.accept("b3")).toBe(true);
    await discarding;
    flushSync();

    expect(manager.review.outcome).toBeNull();
  });

  it("is gone for good after a save, even one from a widget's toolbar", async () => {
    const { manager } = await notMovedByAFailedSave();

    expect(await manager.flushSave()).toBe(true);
    commitGeometryEdit(widgetSeam(manager), "b3", [0.3, 0.3, 0.2, 0.2]);

    expect(manager.review.outcome).toBeNull();
  });

  it("is gone for good after a save that fails as well: it no longer says why the record stays", async () => {
    const { manager, backend } = await notMovedByStagedWork();
    manager.review.accept("b1");

    backend.failWrites = new Error("backend down");
    expect(await manager.review.save()).toBe(false);

    expect(manager.review.outcome).toBeNull();
  });

  it("is gone for good once the work it stopped on is let go, nothing else unsaved", async () => {
    const { manager, flag } = await notMovedByStagedWork();

    flag.set(false);
    // What the screen does between two gestures.
    flushSync();
    manager.review.accept("b1");

    expect(manager.review.outcome).toBeNull();
  });

  it("stays while the work it stopped on is there, though that work changes", async () => {
    const { manager } = await notMovedByStagedWork();

    manager.review.accept("b1");
    flushSync();

    expect(manager.review.outcome).toEqual({ kind: "not-saved" });
  });

  it("is gone for good once another record is opened, even coming back", async () => {
    const { manager } = await notMovedByAFailedSave();

    await manager.openRecord(DATASET_ID, REC_2, VIEWPORT);
    await manager.openRecord(DATASET_ID, REC_1, VIEWPORT);
    manager.review.accept("b1");

    expect(manager.review.outcome).toBeNull();
  });

  it("any message about a record is forgotten once another one is opened, even coming back", async () => {
    const { manager } = await openManager(twoRecords(), {
      next: { recordId: null, remaining: 0 },
    });
    await manager.review.saveAndNext(VIEWPORT);
    expect(manager.review.outcome?.kind).toBe("none-left");

    await manager.openRecord(DATASET_ID, REC_2, VIEWPORT);
    await manager.openRecord(DATASET_ID, REC_1, VIEWPORT);

    expect(manager.review.outcome).toBeNull();
  });

  it("says the save failed, though a save pressed during its read-back cleared the error", async () => {
    const { manager, backend } = await openManager(
      {
        [REC_1]: { [BBOX_RESOURCE]: [modelBox(REC_1, "b1")] },
        [REC_2]: { [BBOX_RESOURCE]: [modelBox(REC_2, "b2")] },
      },
      { next: { recordId: REC_2, remaining: 1 } },
    );
    manager.review.accept("b1");
    backend.failWrites = new Error("backend down");
    // The failed save reads its entities back, slowly.
    const listing = deferred();
    backend.holdEntityListings = listing.promise;
    backend.log.length = 0;
    const moving = manager.review.saveAndNext(VIEWPORT);
    await vi.waitFor(() => expect(backend.log).toContain("listEntities"));
    backend.holdEntityListings = undefined;

    // Meanwhile the reviewer retries from the Review tab; the backend still down, its answer slow.
    const retryHeld = deferred();
    backend.holdWrites = retryHeld.promise;
    const retry = manager.review.save();
    expect(manager.saveError).toBeNull();
    listing.resolve();
    await moving;

    expect(manager.review.outcome).toEqual({ kind: "not-saved", saveFailed: true });
    backend.holdWrites = undefined;
    retryHeld.resolve();
    expect(await retry).toBe(false);
    expect(manager.review.outcome).toEqual({ kind: "not-saved", saveFailed: true });
  });

  it("says why as it stopped, whatever a later save reports", async () => {
    const { manager } = await notMovedByStagedWork();
    expect(manager.review.outcome).not.toHaveProperty("saveFailed");

    const failed = await notMovedByAFailedSave();
    expect(failed.manager.review.outcome).toMatchObject({ saveFailed: true });
  });
});

describe("ReviewController — Save & next lets go of its lock on every way out", () => {
  function threeRecords() {
    return { ...twoRecords(), [REC_3]: { [BBOX_RESOURCE]: [modelBox(REC_3, "b3")] } };
  }

  it("on another record opened from the list while it looks: decisions there are taken", async () => {
    const lookup = deferred<NextRecordToReview>();
    const { manager, backend } = await openManager(threeRecords(), { next: lookup.promise });

    const { moving } = await saveAndNextUpToTheLookup(manager, backend.log);
    await manager.openRecord(DATASET_ID, REC_3, VIEWPORT);

    expect(manager.review.navigating).toBe(false);
    expect(deleteGestureFor(manager.annotations.find("b3")!, widgetSeam(manager).mutations)).toBe(
      "reject",
    );
    expect(manager.review.accept("b3")).toBe(true);
    lookup.resolve({ recordId: REC_2, remaining: 1 });
    await moving;
    expect(manager.recordId).toBe(REC_3);
  });

  it("on the same record opened again from the list: the run moves nobody", async () => {
    const lookup = deferred<NextRecordToReview>();
    const { manager, backend } = await openManager(threeRecords(), { next: lookup.promise });

    const { moving } = await saveAndNextUpToTheLookup(manager, backend.log);
    await manager.openRecord(DATASET_ID, REC_3, VIEWPORT);
    await manager.openRecord(DATASET_ID, REC_1, VIEWPORT);
    expect(manager.review.accept("b1")).toBe(true);
    lookup.resolve({ recordId: REC_2, remaining: 1 });
    await moving;

    expect(manager.recordId).toBe(REC_1);
    expect(manager.pendingCount).toBe(1);
    expect(manager.review.outcome).toBeNull();
  });

  it("on the record it saves opened again from the list while it looks: decisions are back, and it moves nobody", async () => {
    const lookup = deferred<NextRecordToReview>();
    const { manager, backend } = await openManager(threeRecords(), { next: lookup.promise });

    const { moving } = await saveAndNextUpToTheLookup(manager, backend.log);
    await manager.openRecord(DATASET_ID, REC_1, VIEWPORT);

    expect(manager.review.navigating).toBe(false);
    expect(manager.review.accept("b1")).toBe(true);
    lookup.resolve({ recordId: REC_2, remaining: 1 });
    await moving;
    expect(manager.recordId).toBe(REC_1);
    expect(manager.pendingCount).toBe(1);
    expect(manager.review.outcome).toBeNull();
  });

  it("on the record it saves opened again from the list while it saves: decisions are back, and it moves nobody", async () => {
    const { manager, backend } = await openManager(threeRecords(), {
      next: { recordId: REC_2, remaining: 1 },
    });
    manager.review.accept("b1");
    const writeHeld = deferred();
    backend.holdWrites = writeHeld.promise;
    const moving = manager.review.saveAndNext(VIEWPORT);
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));

    await manager.openRecord(DATASET_ID, REC_1, VIEWPORT);
    expect(manager.review.navigating).toBe(false);
    expect(manager.review.reject("b1")).toBe(true);
    backend.holdWrites = undefined;
    writeHeld.resolve();
    await moving;

    expect(manager.recordId).toBe(REC_1);
    // The Reject stands: the row is gone, and its delete is queued.
    expect(manager.annotations.find("b1")).toBeUndefined();
    expect(manager.pendingMutations).toEqual([
      expect.objectContaining({ op: "delete", resource: BBOX_RESOURCE, id: "b1" }),
    ]);
    expect(manager.review.outcome).toBeNull();
  });

  it("a run left behind lets go of nothing a later run holds, and reports nothing", async () => {
    let failLookup!: (err: Error) => void;
    const lookup = new Promise<NextRecordToReview>((_resolve, reject) => (failLookup = reject));
    const { manager, backend } = await openManager(threeRecords(), { next: lookup });

    const { moving } = await saveAndNextUpToTheLookup(manager, backend.log);
    await manager.openRecord(DATASET_ID, REC_3, VIEWPORT);
    // A run on record 3, held while it saves.
    manager.review.accept("b3");
    const writeHeld = deferred();
    backend.holdWrites = writeHeld.promise;
    const second = manager.review.saveAndNext(VIEWPORT);
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    expect(manager.review.navigating).toBe(true);

    // The first run's lookup fails: it is over, and the second still holds record 3.
    failLookup(new Error("network down"));
    await moving;
    expect(manager.review.navigating).toBe(true);
    expect(manager.review.reject("b3")).toBe(false);
    expect(manager.review.outcome).toBeNull();

    backend.holdWrites = undefined;
    writeHeld.resolve();
    await second;
    expect(manager.review.navigating).toBe(false);
  });

  it("when the save stops it, and when the lookup fails", async () => {
    const { manager, backend } = await openManager(twoRecords(), {
      next: new Error("network down"),
    });
    manager.review.accept("b1");
    backend.failWrites = new Error("backend down");

    await manager.review.saveAndNext(VIEWPORT);
    expect(manager.review.navigating).toBe(false);
    backend.failWrites = undefined;
    await manager.review.saveAndNext(VIEWPORT);
    expect(manager.review.outcome).toEqual({ kind: "failed", message: "network down" });
    expect(manager.review.navigating).toBe(false);
  });
});

describe("Staged work — each holder's own flag", () => {
  /** The record open with two widgets: a point cloud and an image, each with its seam. */
  async function twoWidgets() {
    const opened = await openManager(twoRecords());
    const pointCloud = widgetSeam(opened.manager, "point-cloud-widget");
    const image = widgetSeam(opened.manager, "image-widget");
    return { ...opened, pointCloud, image };
  }

  it("Discard asks every holder to drop its work, and is offered with nothing queued", async () => {
    const { manager, pointCloud, image } = await twoWidgets();
    const dropped: string[] = [];
    const held = pointCloud.claimStagedWork!(() => {
      dropped.push("point cloud");
      held.set(false);
    });
    // A holder that drops its work but forgets its flag: Discard lowers it anyway.
    const polygon = image.claimStagedWork!(() => dropped.push("polygon"));
    const idle = image.claimStagedWork!(() => dropped.push("idle"));
    held.set(true);
    polygon.set(true);
    idle.set(false);

    expect(manager.pendingCount).toBe(0);
    expect(manager.review.canDiscard).toBe(true);
    await manager.review.discard();

    expect(dropped.sort()).toEqual(["point cloud", "polygon"]);
    expect(manager.review.canDiscard).toBe(false);
    expect(await manager.review.save()).toBe(true);
  });

  it("lets go of every flag once another record is opened", async () => {
    const { manager, pointCloud, image } = await twoWidgets();
    pointCloud.claimStagedWork!(() => {}).set(true);
    image.claimStagedWork!(() => {}).set(true);
    expect(manager.unsavedCount).toBe(2);

    // The widgets that held the work close with the record they showed.
    await manager.openRecord(DATASET_ID, REC_2, VIEWPORT);
    expect(manager.hasUnsavedWork).toBe(false);

    // A flag of the new record, raised and lowered, brings none of them back.
    const fresh = widgetSeam(manager).claimStagedWork!(() => {});
    fresh.set(true);
    fresh.set(false);
    expect(manager.hasUnsavedWork).toBe(false);
  });

  it("a widget's staged work can be dropped alone, another widget's kept", async () => {
    const { manager, pointCloud, image } = await twoWidgets();
    const dropped: string[] = [];
    const held = pointCloud.claimStagedWork!(() => dropped.push("point cloud"));
    // A holder that drops its work but forgets its flag: it is lowered anyway.
    const resize = image.claimStagedWork!(() => dropped.push("resize"));
    held.set(true);
    resize.set(true);

    manager.discardStagedWork("image-widget");

    expect(dropped).toEqual(["resize"]);
    expect(manager.unsavedCount).toBe(1);
    held.set(false);
    expect(manager.hasUnsavedWork).toBe(false);
  });
});

describe("ReviewController — list, chips and counts", () => {
  it("lists the record's annotations the chips let through, with their review", async () => {
    const { manager } = await openManager({
      [REC_1]: {
        [BBOX_RESOURCE]: [
          modelBox(REC_1, "b1"),
          modelBox(REC_1, "b2", "accepted"),
          humanBox(REC_1, "h1"),
        ],
      },
    });

    // No chip is off by default.
    expect(manager.review.rows.map((r) => r.id)).toEqual(["b1", "b2", "h1"]);
    expect(manager.review.rows[0]).toMatchObject({
      kind: "bbox",
      source: "yolo",
      modelVersion: "v8",
      confidence: 0.87,
      filterKey: REVIEW_STATUS.PENDING,
      canAccept: true,
      acceptRefusal: null,
      canReject: true,
      rejectRefusal: null,
    });
    // An accepted row can still be rejected, which deletes it.
    expect(manager.review.rows[1]).toMatchObject({
      filterKey: REVIEW_STATUS.ACCEPTED,
      canAccept: false,
      acceptRefusal: "accepted",
      canReject: true,
      rejectRefusal: null,
    });
    // A person's row takes no decision, so none is refused either.
    expect(manager.review.rows[2]).toMatchObject({
      filterKey: HUMAN_REVIEW_FILTER,
      source: "",
      canAccept: false,
      acceptRefusal: null,
      canReject: false,
      rejectRefusal: null,
    });
    expect(manager.review.counts).toEqual({ pending: 1, accepted: 1, human: 1 });
  });

  it("toggles a chip by assigning a new filter, and shows the rows back", async () => {
    const { manager } = await openManager({
      [REC_1]: { [BBOX_RESOURCE]: [modelBox(REC_1, "b1", "accepted")] },
    });
    manager.review.toggle(REVIEW_STATUS.ACCEPTED);
    expect(manager.review.isHidden(REVIEW_STATUS.ACCEPTED)).toBe(true);
    expect(manager.review.rows).toEqual([]);

    manager.review.toggle(REVIEW_STATUS.ACCEPTED);

    expect(manager.review.isHidden(REVIEW_STATUS.ACCEPTED)).toBe(false);
    expect(manager.review.rows.map((r) => r.id)).toEqual(["b1"]);
  });

  it("follows the canvas selection, and selects for the canvas", async () => {
    const { manager } = await openManager(twoRecords());

    manager.annotations.select("h1");
    expect(manager.review.rows.find((r) => r.selected)?.id).toBe("h1");

    manager.review.select("b1");
    expect(manager.annotations.selectedId).toBe("b1");
  });

  it("stamps its own source on the decisions it queues, and counts the record's unsaved work", async () => {
    const { manager } = await openManager(twoRecords());

    manager.review.accept("b1");

    expect(manager.pendingMutations[0].widgetId).toBe(REVIEW_PANEL_SOURCE_ID);
    expect(manager.review.unsavedCount).toBe(1);
    expect(manager.review.canSave).toBe(true);
  });

  it("counts the record's unsaved work, whoever made it, once per annotation", async () => {
    const { manager } = await openManager({
      [REC_1]: {
        [BBOX_RESOURCE]: [modelBox(REC_1, "b1"), modelBox(REC_1, "b2"), modelBox(REC_1, "b3")],
      },
    });
    const seam = widgetSeam(manager);

    commitGeometryEdit(seam, "b1", [0.3, 0.3, 0.2, 0.2]);
    expect(manager.review.unsavedCount).toBe(1);
    pressDelete(seam, "b2");
    expect(manager.review.unsavedCount).toBe(2);
    // A new entity and the update pointing at it: two writes, one annotation.
    reassignEntity(
      manager.annotations.find("b3")!,
      { mode: "new", entityFields: { category: "cat" } },
      seam,
    );
    expect(manager.pendingCount).toBe(4);
    expect(manager.review.unsavedCount).toBe(3);
  });

  it("gives the work to the gesture that last changed it", async () => {
    const { manager } = await openManager(twoRecords());

    manager.review.accept("b1");
    commitGeometryEdit(widgetSeam(manager), "b1", [0.3, 0.3, 0.2, 0.2]);

    // The canvas's edit replaced the controller's decision: it is the canvas's work.
    expect(manager.pendingMutations.map((m) => m.widgetId)).toEqual(["image-widget"]);
  });

  it("saves the record's unsaved work, and has nothing left to save", async () => {
    const { manager, backend } = await openManager(twoRecords());
    manager.review.accept("b1");

    expect(await manager.review.save()).toBe(true);

    expect(backend.writes).toEqual([
      { op: "update", resource: BBOX_RESOURCE, id: "b1", body: { review_status: "accepted" } },
    ]);
    expect(manager.review.canSave).toBe(false);
    expect(manager.review.unsavedCount).toBe(0);
  });

  it("discards the record's unsaved work", async () => {
    const { manager } = await openManager(twoRecords());
    manager.review.accept("b1");

    await manager.review.discard();

    expect(manager.pendingCount).toBe(0);
    expect(manager.annotations.find("b1")?.review?.status).toBe(REVIEW_STATUS.PENDING);
  });

  it("lists only the annotations of the entities the Entities tab shows", async () => {
    const { manager } = await openManager({
      [REC_1]: { [BBOX_RESOURCE]: [modelBox(REC_1, "b1"), modelBox(REC_1, "b2")] },
    });

    manager.toggleEntityVisible("ent-b1");

    expect(manager.review.rows.map((r) => r.id)).toEqual(["b1"]);
  });

  it("drops the selection of a row Reject removes", async () => {
    const { manager } = await openManager(twoRecords());
    manager.review.select("b1");

    expect(manager.review.reject("b1")).toBe(true);

    expect(manager.annotations.find("b1")).toBeUndefined();
    expect(manager.annotations.selectedId).toBeNull();
  });

  it("drops the selection of a row the Accepted chip hides once it is accepted", async () => {
    const { manager } = await openManager(twoRecords());
    manager.review.toggle(REVIEW_STATUS.ACCEPTED);
    manager.review.select("b1");

    manager.review.accept("b1");

    expect(manager.annotations.selectedId).toBeNull();
  });

  it("refuses Reject on what is not a model's stored row", async () => {
    const { manager } = await openManager(twoRecords());

    expect(manager.review.reject("h1")).toBe(false);
    expect(manager.review.reject("not-there")).toBe(false);
    expect(manager.annotations.find("h1")).toBeDefined();
    expect(manager.pendingCount).toBe(0);
  });

  it("lists a draft as a person's work, with no decision to offer", async () => {
    const { manager } = await openManager(twoRecords());
    manager.annotations.add({
      id: "draft",
      entityId: "",
      kind: "bbox",
      viewId: viewIdOf(REC_1),
      geometry: [0, 0, 0.1, 0.1],
      persisted: false,
    });
    manager.review.toggle(HUMAN_REVIEW_FILTER);

    // Drafts always show, whatever the chips say.
    expect(manager.review.rows.find((r) => r.id === "draft")).toMatchObject({
      persisted: false,
      filterKey: HUMAN_REVIEW_FILTER,
      canAccept: false,
      canReject: false,
    });
  });
});

describe("WorkspaceManager.openRecord", () => {
  it("drops the previous record's unsaved work and loads the new one", async () => {
    const { manager } = await openManager(twoRecords());
    manager.review.accept("b1");

    await manager.openRecord(DATASET_ID, REC_2);

    expect(manager.recordId).toBe(REC_2);
    expect(manager.pendingCount).toBe(0);
    expect(manager.annotations.items.map((a) => a.id)).toEqual(["b2"]);
  });
});
