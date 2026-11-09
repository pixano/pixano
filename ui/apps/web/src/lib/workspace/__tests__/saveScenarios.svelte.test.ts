/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import {
  DATASET_ID,
  deferred,
  drag,
  entityOf,
  geometryOf,
  humanBox,
  MODEL_METADATA,
  modelBox,
  MOVED,
  openManager,
  openWithBoxes,
  REC,
  refusal,
  rowOf,
  serveLikeTheApi,
  statusOf,
  STORED,
  updatesSent,
  viewIdOf,
  VIEWPORT,
  widgetSeam,
  type FakeBackend,
} from "./workspaceHarness.js";
import type { BBoxGeometry } from "$lib/annotations/annotationCollection.svelte.js";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import { commitNewAnnotation, reassignEntity } from "$lib/annotations/payloadBuilders.js";
import { REVIEW_STATUS } from "$lib/annotations/reviewStatus.js";
import type { SeamContext } from "$lib/annotations/scene/sceneContext.js";
import { deleteAnnotation } from "$lib/api/annotations.js";
import { ApiError } from "$lib/api/apiClient.js";

// What a save does with the work around it, run through the real workspace —
// manager, mutation queue, record loader, commit helpers — over a recording
// fake backend: work begun while a request is on the wire, the entities a save
// creates, and when a read-back lands.

/** A 5xx a proxy answers after the server stored the write: no refusal, so it may have been stored. */
const GATEWAY_TIMEOUT = new ApiError("Gateway Timeout", 504, "");

/** Where a first drag puts a box, before one to `MOVED`. */
const DRAGGED_FIRST: BBoxGeometry = [0.2, 0.2, 0.2, 0.2];
/** Where a last drag puts a box, after one to `MOVED`. */
const DRAGGED_LAST: BBoxGeometry = [0.5, 0.5, 0.2, 0.2];

/** The status of a write refused because another writer holds the dataset. */
const HTTP_CONFLICT = 409;

/**
 * The error the real HTTP module throws for an annotation delete the server
 * answers with `status` — what the HTTP gateway hands the queue.
 */
async function refusalOfARealDelete(status: number): Promise<unknown> {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify({ detail: "busy" }), { status }))),
  );
  try {
    await deleteAnnotation(DATASET_ID, BBOX_RESOURCE, "h1");
  } catch (err) {
    return err;
  } finally {
    vi.unstubAllGlobals();
  }
  throw new Error(`a delete answered ${status} did not fail`);
}

/**
 * Store each write as the server would for these boxes: an Accept stores the
 * status, a change of content stores the content, accepted; a new entity is
 * listed with the record's entities.
 */
function storeWrites(backend: FakeBackend): void {
  backend.onWrite = (write) => {
    if (write.op === "create" && write.resource === "entities") {
      backend.entities.push({ ...(write.body as { id: string; record_id: string }) });
      return;
    }
    if (write.op !== "update") return;
    const row = backend.records[REC][BBOX_RESOURCE].find((r) => r.id === write.id)!;
    const { review_status: status, ...content } = write.body;
    if (status !== undefined) row.review_status = status;
    if (Object.keys(content).length > 0) Object.assign(row, content, { review_status: "accepted" });
  };
}

/** A box drawn and waiting for its entity, as the draw tools leave it. */
function drawDraftAwaitingEntity(seam: SeamContext): void {
  seam.collection.add({
    id: "draft",
    entityId: "",
    kind: "bbox",
    viewId: viewIdOf(REC),
    geometry: MOVED,
    persisted: false,
  });
  seam.beginPendingAnnotation({ label: "box", onConfirm: () => {}, onCancel: () => {} });
}

describe("flushSave reads back what the server stored", () => {
  it("stores a person's edit of a model's row accepted, the model's provenance and score kept", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    serveLikeTheApi(backend, REC);

    drag(seam, "b1");
    expect(await manager.flushSave()).toBe(true);

    const stored = {
      coords: MOVED,
      review_status: "accepted",
      source_type: "model",
      source_name: "detection",
      source_metadata: MODEL_METADATA,
      confidence: 0.87,
    };
    expect(backend.records[REC][BBOX_RESOURCE][0]).toMatchObject(stored);
    expect(manager.annotations.find("b1")?.review).toMatchObject({
      status: REVIEW_STATUS.ACCEPTED,
      sourceType: "model",
      confidence: 0.87,
    });
  });

  it("an edit of a row someone else deleted is refused, and stays queued", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    serveLikeTheApi(backend, REC);
    backend.records[REC][BBOX_RESOURCE] = [];

    drag(seam, "b1");
    expect(await manager.flushSave()).toBe(false);

    expect(manager.saveError).toContain("not found");
    expect(manager.pendingCount).toBe(1);
  });

  it("puts on screen the row as the server stored it", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    // What the server stores for a model's row a person moved — here with
    // coordinates of its own, which only a read-back can bring to the screen.
    const serverCoords = [0.25, 0.25, 0.2, 0.2];
    backend.onWrite = (write) => {
      if (write.op !== "update") return;
      Object.assign(backend.records[REC][BBOX_RESOURCE][0], {
        review_status: "accepted",
        coords: serverCoords,
      });
    };

    drag(seam, "b1");
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
    expect(await manager.flushSave()).toBe(true);

    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
    expect(geometryOf(manager, "b1")).toEqual(serverCoords);
  });

  it("reloads the entities before the annotations, so a reassigned box keeps its label", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    // What the server stores: the new entity, and the box pointing at it.
    backend.onWrite = (write) => {
      if (write.op === "create" && write.resource === "entities") {
        backend.entities.push({ ...(write.body as { id: string; record_id: string }) });
      }
      if (write.op === "update") {
        backend.records[REC][BBOX_RESOURCE][0].entity_id = write.body.entity_id as string;
      }
    };

    reassignEntity(
      manager.annotations.find("b1")!,
      { mode: "new", entityFields: { category: "cat" } },
      seam,
    );
    backend.log.length = 0;
    await manager.flushSave();

    expect(manager.annotations.find("b1")?.entity).toMatchObject({ category: "cat" });
    expect(backend.log.indexOf("listEntities")).toBeLessThan(
      backend.log.indexOf(`list ${BBOX_RESOURCE}`),
    );
  });

  it("keeps a draft drawn while the save was in flight", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    let releaseWrites!: () => void;
    backend.holdWrites = new Promise((resolve) => (releaseWrites = resolve));

    manager.review.accept("b1");
    const saving = manager.flushSave();
    // Drawn as the draw tools do: into the collection, then waiting for its entity.
    seam.collection.add({
      id: "draft",
      entityId: "",
      kind: "bbox",
      viewId: viewIdOf(REC),
      geometry: MOVED,
      persisted: false,
    });
    seam.beginPendingAnnotation({ label: "box", onConfirm: () => {}, onCancel: () => {} });
    releaseWrites();

    // The decision went through, but the record is not all saved: the draft is not.
    expect(await saving).toBe(false);
    expect(backend.writes).toHaveLength(1);
    expect(manager.annotations.find("draft")).toBeDefined();
    expect(manager.pendingAnnotation).not.toBeNull();
  });

  it("keeps a draft drawn while the save was reading back", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    let releaseListings!: () => void;
    backend.holdListings = new Promise((resolve) => (releaseListings = resolve));

    manager.review.accept("b1");
    backend.log.length = 0; // forget the record's opening reads
    const saving = manager.flushSave();
    // The save has written and is now reading the annotations back.
    await vi.waitFor(() => expect(backend.log).toContain(`list ${BBOX_RESOURCE}`));
    seam.collection.add({
      id: "draft",
      entityId: "",
      kind: "bbox",
      viewId: viewIdOf(REC),
      geometry: MOVED,
      persisted: false,
    });
    seam.beginPendingAnnotation({ label: "box", onConfirm: () => {}, onCancel: () => {} });
    releaseListings();
    await saving;

    expect(manager.annotations.find("draft")).toBeDefined();
  });

  it("keeps the decision queued and reports a failed save", async () => {
    const { manager, backend } = await openWithBoxes(modelBox(REC, "b1"));
    backend.failWrites = new Error("backend down");

    manager.review.accept("b1");
    expect(await manager.flushSave()).toBe(false);

    expect(manager.pendingCount).toBe(1);
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
  });
});

describe("Work begun while a save is on the wire", () => {
  it("a decision on the row being sent is kept for the next save", async () => {
    const { manager, backend } = await openWithBoxes(modelBox(REC, "b1"));
    serveLikeTheApi(backend, REC);
    const held = deferred();
    backend.holdWrites = held.promise;

    manager.review.accept("b1");
    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    expect(manager.review.reject("b1")).toBe(true);
    backend.holdWrites = undefined;
    held.resolve();

    // The Reject was not sent, so the record is not all saved.
    expect(await saving).toBe(false);
    expect(manager.pendingCount).toBe(1);
    expect(await manager.flushSave()).toBe(true);
    expect(backend.writes).toEqual([
      { op: "update", resource: BBOX_RESOURCE, id: "b1", body: { review_status: "accepted" } },
      { op: "delete", resource: BBOX_RESOURCE, id: "b1" },
    ]);
    expect(backend.records[REC][BBOX_RESOURCE]).toEqual([]);
  });

  it("an edit queued behind the request on the wire is not sent once a Reject drops it, and its delete is", async () => {
    const { manager, backend, seam } = await openWithBoxes(
      modelBox(REC, "b1"),
      modelBox(REC, "b2"),
    );
    drag(seam, "b1");
    drag(seam, "b2");
    const held = deferred();
    backend.holdWrites = held.promise;

    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    manager.review.reject("b2");
    backend.holdWrites = undefined;
    held.resolve();
    await saving;
    await manager.flushSave();

    expect(updatesSent(backend).filter((w) => w.op === "update" && w.id === "b2")).toEqual([]);
    expect(backend.writes.filter((w) => w.op === "delete")).toEqual([
      { op: "delete", resource: BBOX_RESOURCE, id: "b2" },
    ]);
  });

  /** Commit a box with its entity, then hold its create on the wire, the entity stored. */
  async function draftWithCreateOnTheWire() {
    const opened = await openWithBoxes();
    const { backend, seam, manager } = opened;
    serveLikeTheApi(backend, REC);
    const draft = commitNewAnnotation(seam, "bbox", STORED);
    const entityHeld = deferred();
    backend.holdWrites = entityHeld.promise;
    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain("create entities"));
    // The entity lands; the box's create is held.
    const createHeld = deferred();
    backend.holdWrites = createHeld.promise;
    entityHeld.resolve();
    await vi.waitFor(() => expect(backend.log).toContain(`create ${BBOX_RESOURCE}`));
    const release = () => {
      backend.holdWrites = undefined;
      createHeld.resolve();
    };
    return { ...opened, draft, saving, release };
  }

  it("an edit of a box whose create is on the wire follows it as an update", async () => {
    const { manager, backend, seam, draft, saving, release } = await draftWithCreateOnTheWire();

    drag(seam, draft.id);
    release();

    await saving;
    await manager.flushSave();
    const updates = updatesSent(backend);
    expect(updates).toHaveLength(1);
    expect(updates[0]).toMatchObject({ id: draft.id, body: { coords: MOVED } });
  });

  it("an edit of a box whose create failed, with an update behind it, is the one sent last", async () => {
    const { manager, backend, seam, draft, saving, release } = await draftWithCreateOnTheWire();

    // An update queued behind the create on the wire, which then fails.
    drag(seam, draft.id);
    backend.failWrites = new Error("network down");
    release();
    await saving;
    backend.failWrites = undefined;
    // The queue holds the create again, then that update: a new drag goes into the latter.
    drag(seam, draft.id, DRAGGED_LAST);
    await manager.flushSave();

    expect(updatesSent(backend).at(-1)).toMatchObject({
      id: draft.id,
      body: { coords: DRAGGED_LAST },
    });
    expect(backend.records[REC][BBOX_RESOURCE]).toEqual([
      expect.objectContaining({ id: draft.id, coords: DRAGGED_LAST }),
    ]);
    expect(geometryOf(manager, draft.id)).toEqual(DRAGGED_LAST);
  });

  it("a box deleted while its create is on the wire is deleted once it lands", async () => {
    const { manager, backend, draft, saving, release } = await draftWithCreateOnTheWire();

    manager.deleteAnnotation(manager.annotations.find(draft.id)!, "image-widget");
    release();

    await saving;
    await manager.flushSave();
    expect(backend.writes.at(-1)).toEqual({ op: "delete", resource: BBOX_RESOURCE, id: draft.id });
  });

  it("a box deleted while its create is on the wire leaves nothing to send if the server refuses that create", async () => {
    const { manager, backend, draft, saving, release } = await draftWithCreateOnTheWire();
    const serve = backend.onWrite!;
    // Refused for good, as an invalid body is: the server stored nothing.
    backend.onWrite = (write) => {
      if (write.op === "create" && write.resource === BBOX_RESOURCE) throw refusal("Invalid data");
      serve(write);
    };

    manager.deleteAnnotation(manager.annotations.find(draft.id)!, "image-widget");
    release();
    await saving;

    // There is no row to create again, nor one to delete, nor a failure to report.
    expect(manager.saveError).toBeNull();
    expect(manager.pendingMutations).toEqual([]);
    expect(backend.writes.filter((w) => w.resource === BBOX_RESOURCE)).toEqual([]);
  });

  it("a box deleted while its create is on the wire leaves no box behind if that create is lost on the way", async () => {
    const { manager, backend, draft, saving, release } = await draftWithCreateOnTheWire();

    manager.deleteAnnotation(manager.annotations.find(draft.id)!, "image-widget");
    // Nothing reached the server: the create may as well have, so its undoing stays.
    backend.failWrites = new Error("network down");
    release();
    await saving;
    expect(manager.saveError).toBe("network down");
    backend.failWrites = undefined;

    await manager.flushSave();
    expect(manager.pendingCount).toBe(0);
    expect(backend.records[REC][BBOX_RESOURCE]).toEqual([]);
  });

  it.each([
    ["the connection reset", new Error("connection reset")],
    ["a proxy's 5xx", GATEWAY_TIMEOUT],
  ])(
    "a box deleted while its create is on the wire leaves nothing behind if that create's answer is lost — %s",
    async (_answer, lostAnswer) => {
      const { manager, backend, draft, saving, release } = await draftWithCreateOnTheWire();

      manager.deleteAnnotation(manager.annotations.find(draft.id)!, "image-widget");
      // The server stored the box; its answer never came back. A 5xx is no
      // refusal: it says nothing of what was stored.
      backend.loseAnswers = lostAnswer;
      release();
      await saving;
      backend.loseAnswers = undefined;
      expect(backend.records[REC][BBOX_RESOURCE].map((row) => row.id)).toEqual([draft.id]);

      await manager.flushSave();
      expect(backend.records[REC][BBOX_RESOURCE]).toEqual([]);
      expect(backend.entities).toEqual([]);
      expect(manager.annotations.find(draft.id)).toBeUndefined();
    },
  );

  /**
   * Box b1 dragged to `DRAGGED_FIRST` and saved, a drag to `MOVED` queued
   * behind that edit on the wire, which then fails. The backend stores every
   * write as the server does.
   */
  async function failedEditWithAnotherBehind() {
    const opened = await openWithBoxes(humanBox(REC, "b1"));
    const { manager, backend, seam } = opened;
    serveLikeTheApi(backend, REC);
    const held = deferred();
    backend.holdWrites = held.promise;

    drag(seam, "b1", DRAGGED_FIRST);
    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    drag(seam, "b1", MOVED);
    backend.failWrites = new Error("network down");
    held.resolve();
    await saving;
    backend.holdWrites = undefined;
    backend.failWrites = undefined;
    return opened;
  }

  /** The coordinates of each update the workspace sent, in the order it sent them. */
  const coordsSent = (backend: FakeBackend) =>
    updatesSent(backend).map((w) => w.op === "update" && w.body.coords);

  it("a failed edit is sent again ahead of the edit queued behind it while it was on the wire", async () => {
    const { manager, backend } = await failedEditWithAnotherBehind();

    await manager.flushSave();

    expect(coordsSent(backend)).toEqual([DRAGGED_FIRST, MOVED]);
    expect(backend.records[REC][BBOX_RESOURCE][0].coords).toEqual(MOVED);
  });

  it("an edit made after a failed save replaces the one queued behind it, and is sent last", async () => {
    const { manager, backend, seam } = await failedEditWithAnotherBehind();

    // The queue holds the failed edit again, then the drag to MOVED: a new drag replaces the latter.
    drag(seam, "b1", DRAGGED_LAST);
    await manager.flushSave();

    expect(coordsSent(backend)).toEqual([DRAGGED_FIRST, DRAGGED_LAST]);
    expect(backend.records[REC][BBOX_RESOURCE][0].coords).toEqual(DRAGGED_LAST);
  });

  it("an edit made after a failed save is the one sent last", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    const FIRST: BBoxGeometry = [0.2, 0.2, 0.2, 0.2];
    serveLikeTheApi(backend, REC);
    const held = deferred();
    backend.holdWrites = held.promise;

    manager.review.accept("b1");
    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    // A drag queued behind the Accept on the wire, which then fails.
    drag(seam, "b1", FIRST);
    backend.failWrites = new Error("network down");
    held.resolve();
    expect(await saving).toBe(false);
    backend.holdWrites = undefined;
    backend.failWrites = undefined;
    // The queue holds the Accept again, then the drag. A second drag replaces the latter.
    drag(seam, "b1", MOVED);
    expect(await manager.flushSave()).toBe(true);

    expect(updatesSent(backend).map((w) => w.op === "update" && w.body.coords)).toEqual([
      undefined,
      MOVED,
    ]);
    expect(backend.records[REC][BBOX_RESOURCE][0]).toMatchObject({
      coords: MOVED,
      review_status: "accepted",
    });
  });

  it("a draft deleted while its entity's create is on the wire: its box create is never sent", async () => {
    const { manager, backend, seam } = await openWithBoxes();
    serveLikeTheApi(backend, REC);
    const draft = commitNewAnnotation(seam, "bbox", STORED);
    const held = deferred();
    backend.holdWrites = held.promise;
    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain("create entities"));

    manager.deleteAnnotation(manager.annotations.find(draft.id)!, "image-widget");
    backend.holdWrites = undefined;
    held.resolve();
    await saving;

    expect(backend.writes.filter((w) => w.resource === BBOX_RESOURCE)).toEqual([]);
    expect(manager.annotations.find(draft.id)).toBeUndefined();
  });

  it("moving a box onto a new entity while the save sends sends that entity first", async () => {
    const { manager, backend, seam } = await openWithBoxes(humanBox(REC, "x"), humanBox(REC, "y"));
    drag(seam, "x");
    drag(seam, "y");
    const held = deferred();
    backend.holdWrites = held.promise;

    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    // x's update is on the wire; y's is queued in this save, and now names an
    // entity whose create was queued after the save began.
    reassignEntity(
      manager.annotations.find("y")!,
      { mode: "new", entityFields: { category: "cat" } },
      seam,
    );
    const entityId = manager.annotations.find("y")!.entityId;
    backend.holdWrites = undefined;
    held.resolve();

    await saving;
    const order = backend.writes.map((w) => (w.op === "create" ? w.body.id : w.id));
    expect(order).toEqual(["x", entityId, "y"]);
    expect(backend.writes.at(-1)).toMatchObject({ body: { entity_id: entityId } });
  });
});

describe("An entity created during a save, sent ahead of the write naming it", () => {
  const ENTITIES = [entityOf(REC, "ent-x"), entityOf(REC, "ent-y")];

  /**
   * Boxes x and y, each with an edit queued, a save started with x's write on
   * the wire; y is then moved onto a new entity, whose create the save sends
   * ahead of y's write — and holds on the wire. The backend stores every write
   * as the server does.
   */
  async function entityCreateOnTheWire() {
    const opened = await openManager(
      { [REC]: { [BBOX_RESOURCE]: [humanBox(REC, "x"), humanBox(REC, "y")] } },
      { entities: ENTITIES.map((entity) => ({ ...entity })) },
    );
    const { manager, backend } = opened;
    const seam = widgetSeam(manager);
    serveLikeTheApi(backend, REC);
    drag(seam, "x");
    drag(seam, "y");
    const xHeld = deferred();
    backend.holdWrites = xHeld.promise;
    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    reassignEntity(
      manager.annotations.find("y")!,
      { mode: "new", entityFields: { category: "cat" } },
      seam,
    );
    const entityId = manager.annotations.find("y")!.entityId;
    const entityHeld = deferred();
    backend.holdWrites = entityHeld.promise;
    xHeld.resolve();
    await vi.waitFor(() => expect(backend.log).toContain("create entities"));
    const release = () => {
      backend.holdWrites = undefined;
      entityHeld.resolve();
    };
    return { ...opened, seam, saving, entityId, release };
  }

  const yRow = (backend: FakeBackend) =>
    backend.records[REC][BBOX_RESOURCE].find((row) => row.id === "y")!;
  const entityIds = (backend: FakeBackend) => backend.entities.map((entity) => entity.id);
  const yWrites = (backend: FakeBackend) =>
    backend.writes.filter((w) => w.op === "update" && w.id === "y");

  it("a second new entity meanwhile: its create is sent before the write naming it", async () => {
    const { manager, backend, saving, release, seam } = await entityCreateOnTheWire();

    reassignEntity(
      manager.annotations.find("y")!,
      { mode: "new", entityFields: { category: "dog" } },
      seam,
    );
    const secondId = manager.annotations.find("y")!.entityId;
    release();
    await saving;

    // No write named an entity not created yet.
    expect(manager.saveError).toBeNull();
    expect(yWrites(backend).map((w) => w.op === "update" && w.body.entity_id)).toEqual([secondId]);
    await manager.flushSave();
    expect(yRow(backend).entity_id).toBe(secondId);
    expect(entityIds(backend)).toContain(secondId);
  });

  it("Discard meanwhile: the edit it threw away is never sent", async () => {
    const { manager, backend, saving, release } = await entityCreateOnTheWire();

    const discarding = manager.discardChanges();
    release();
    await saving;
    await discarding;

    expect(yWrites(backend)).toEqual([]);
    expect(yRow(backend)).toMatchObject({ coords: STORED, entity_id: "ent-y" });
  });

  it("another record opened meanwhile: the edit left behind is never sent", async () => {
    const { manager, backend, saving, release } = await entityCreateOnTheWire();
    backend.records["rec-2"] = { [BBOX_RESOURCE]: [] };

    const opening = manager.openRecord(DATASET_ID, "rec-2", VIEWPORT);
    release();
    await saving;
    await opening;

    expect(manager.recordId).toBe("rec-2");
    expect(yWrites(backend)).toEqual([]);
  });
});

describe("What the dataset holds, recorded as each write leaves", () => {
  /** What the workspace records the dataset holds of an annotation's content. */
  const storedGeometryOf = (
    manager: Awaited<ReturnType<typeof openManager>>["manager"],
    id: string,
  ) => manager.annotations.find(id)?.persistedContent?.geometry;

  it("records the content a write carried, not an edit made while it was on the wire", async () => {
    const { manager, backend, seam } = await openWithBoxes(humanBox(REC, "b1"));
    drag(seam, "b1");
    const held = deferred();
    backend.holdWrites = held.promise;

    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    drag(seam, "b1", DRAGGED_LAST);
    held.resolve();
    await saving;

    expect(storedGeometryOf(manager, "b1")).toEqual(MOVED);
    expect(geometryOf(manager, "b1")).toEqual(DRAGGED_LAST);
  });

  it("a decision re-sent after a failure does not record an edit queued behind it as stored", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    serveLikeTheApi(backend, REC);
    const firstTry = deferred();
    backend.holdWrites = firstTry.promise;

    manager.review.accept("b1");
    const failing = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    drag(seam, "b1");
    backend.failWrites = new Error("network down");
    firstTry.resolve();
    expect(await failing).toBe(false);
    backend.failWrites = undefined;

    // Saved again: the Accept leaves first, carrying the status alone.
    const retry = deferred();
    backend.holdWrites = retry.promise;
    backend.log.length = 0;
    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    // The box dragged back where the dataset holds it: no edit is left to send —
    // which holds only if the Accept on the wire recorded the stored content,
    // not the drag queued behind it.
    drag(seam, "b1", STORED);
    // The write on the wire is all that is left.
    expect(manager.pendingMutations).toEqual([]);
    backend.holdWrites = undefined;
    retry.resolve();
    expect(await saving).toBe(true);

    expect(backend.writes).toEqual([
      { op: "update", resource: BBOX_RESOURCE, id: "b1", body: { review_status: "accepted" } },
    ]);
    expect(geometryOf(manager, "b1")).toEqual(backend.records[REC][BBOX_RESOURCE][0].coords);
  });

  it("leaves the content recorded as it was when the write fails", async () => {
    const { manager, backend, seam } = await openWithBoxes(humanBox(REC, "b1"));
    backend.failWrites = new Error("backend down");

    drag(seam, "b1");
    expect(await manager.flushSave()).toBe(false);

    expect(storedGeometryOf(manager, "b1")).toEqual(STORED);
  });

  it("records a draft's content once its create has left", async () => {
    const { manager, backend, seam } = await openWithBoxes();
    const draft = commitNewAnnotation(seam, "bbox", MOVED);
    expect(manager.annotations.find(draft.id)?.persistedContent).toBeUndefined();
    // Recorded as the write leaves, not by the save's read-back.
    const read = deferred();
    backend.holdListings = read.promise;
    backend.log.length = 0;

    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`list ${BBOX_RESOURCE}`));

    expect(storedGeometryOf(manager, draft.id)).toEqual(MOVED);
    read.resolve();
    await saving;
  });
});

describe("A read-back never lands over newer work", () => {
  it("rows read before a later save are not shown after it", async () => {
    const { manager, backend, seam } = await openWithBoxes(
      modelBox(REC, "b1"),
      modelBox(REC, "b2"),
    );
    // What the server stores, by its rules, for the two writes made here.
    backend.onWrite = (write) => {
      if (write.op !== "update") return;
      const row = backend.records[REC][BBOX_RESOURCE].find((r) => r.id === write.id)!;
      if ("review_status" in write.body) row.review_status = write.body.review_status;
      else Object.assign(row, { coords: write.body.coords, review_status: "accepted" });
    };

    manager.review.accept("b1");
    const firstRead = deferred();
    backend.holdListings = firstRead.promise;
    backend.log.length = 0;
    const first = manager.flushSave();
    // The first save has read b2 as it is now, and its answer is held.
    await vi.waitFor(() => expect(backend.log).toContain(`list ${BBOX_RESOURCE}`));

    const secondRead = deferred();
    backend.holdListings = secondRead.promise;
    drag(seam, "b2");
    const second = manager.flushSave();
    await vi.waitFor(() =>
      expect(backend.log.filter((call) => call === `list ${BBOX_RESOURCE}`)).toHaveLength(2),
    );
    secondRead.resolve();
    await second;
    firstRead.resolve();
    await first;

    expect(geometryOf(manager, "b2")).toEqual(MOVED);
    expect(statusOf(manager, "b2")).toBe(REVIEW_STATUS.ACCEPTED);
  });

  it("a save's entities read before a later save are not shown after it", async () => {
    const { manager, backend } = await openManager(
      { [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1"), modelBox(REC, "b2")] } },
      { entities: [entityOf(REC, "ent-b1"), entityOf(REC, "ent-b2")] },
    );
    const seam = widgetSeam(manager);
    storeWrites(backend);

    manager.review.accept("b1");
    // The first save's entity listing is read now, and its answer held.
    const firstListing = deferred();
    backend.holdEntityListings = firstListing.promise;
    backend.log.length = 0;
    const first = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain("listEntities"));
    backend.holdEntityListings = undefined;

    reassignEntity(
      manager.annotations.find("b2")!,
      { mode: "new", entityFields: { category: "cat" } },
      seam,
    );
    const entityId = manager.annotations.find("b2")!.entityId;
    expect(await manager.flushSave()).toBe(true);
    firstListing.resolve();
    await first;

    // The first save's listing predates the entity the second one created.
    expect(manager.entities.map((e) => e.id)).toContain(entityId);
    expect(manager.annotations.find("b2")?.entity).toMatchObject({ category: "cat" });
  });

  it("an edit or decision made while a discard reads the rows back stays, on screen and queued", async () => {
    const { manager, backend, seam } = await openWithBoxes(
      modelBox(REC, "b1"),
      modelBox(REC, "b2"),
      modelBox(REC, "b3"),
      humanBox(REC, "h1"),
    );
    // Discarded work: a drag of b2, a deleted person's box.
    drag(seam, "b2");
    manager.deleteAnnotation(manager.annotations.find("h1")!, "image-widget");
    // A row the server holds differently since it was read, which only the read can show.
    backend.records[REC][BBOX_RESOURCE][2].review_status = "accepted";
    const read = deferred();
    backend.holdListings = read.promise;
    backend.log.length = 0;
    const discarding = manager.discardChanges();
    // At once, the record shows what the dataset holds.
    expect(geometryOf(manager, "b2")).toEqual(STORED);
    expect(statusOf(manager, "b2")).toBe(REVIEW_STATUS.PENDING);
    await vi.waitFor(() => expect(backend.log).toContain(`list ${BBOX_RESOURCE}`));
    backend.holdListings = undefined;

    drag(seam, "b1");
    manager.review.accept("b2");
    read.resolve();
    await discarding;

    // The work made during the read, on screen as queued: the edit unsaved, so still pending.
    expect(geometryOf(manager, "b1")).toEqual(MOVED);
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
    expect(geometryOf(manager, "b2")).toEqual(STORED);
    expect(statusOf(manager, "b2")).toBe(REVIEW_STATUS.ACCEPTED);
    expect(manager.pendingMutations.map((m) => m.op === "update" && [m.id, m.body])).toEqual([
      ["b1", expect.objectContaining({ coords: MOVED })],
      ["b2", { review_status: "accepted" }],
    ]);
    // Everything else, as the dataset holds it.
    expect(manager.annotations.find("h1")).toBeDefined();
    expect(statusOf(manager, "b3")).toBe(REVIEW_STATUS.ACCEPTED);
  });

  it("a discard's read-back does not land over a save made after it", async () => {
    const { manager, backend } = await openWithBoxes(modelBox(REC, "b1"));
    backend.onWrite = (write) => {
      if (write.op === "update") {
        backend.records[REC][BBOX_RESOURCE][0].review_status = write.body.review_status;
      }
    };
    const discardRead = deferred();
    backend.holdListings = discardRead.promise;
    backend.log.length = 0;
    const discarding = manager.discardChanges();
    await vi.waitFor(() => expect(backend.log).toContain(`list ${BBOX_RESOURCE}`));

    backend.holdListings = undefined;
    manager.review.accept("b1");
    expect(await manager.flushSave()).toBe(true);
    discardRead.resolve();
    await discarding;

    // The discard read b1 before it was accepted and saved. Two guards keep it
    // off here: the write landed since, and the save's own rows, read later,
    // were taken first. Each is tested alone below.
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
  });

  it("a discard's rows are dropped when a save writes while they are read, even landing first", async () => {
    const { manager, backend } = await openWithBoxes(modelBox(REC, "b1"));
    serveLikeTheApi(backend, REC);
    const discardRead = deferred();
    backend.holdListings = discardRead.promise;
    backend.log.length = 0;
    const discarding = manager.discardChanges();
    await vi.waitFor(() => expect(backend.log).toContain(`list ${BBOX_RESOURCE}`));
    // The save's own rows are read after it, and held, so that the discard's land first.
    const saveRead = deferred();
    backend.holdListings = saveRead.promise;

    manager.review.accept("b1");
    const saving = manager.flushSave();
    await vi.waitFor(() =>
      expect(backend.log.filter((call) => call === `list ${BBOX_RESOURCE}`)).toHaveLength(2),
    );
    discardRead.resolve();
    await discarding;

    // b1 holds no work any more: only the landed write keeps the older rows off.
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
    expect(manager.annotations.find("b1")?.review?.storedStatus).toBe(REVIEW_STATUS.ACCEPTED);
    expect(rowOf(manager, "b1")?.canAccept).toBe(false);
    saveRead.resolve();
    expect(await saving).toBe(true);
  });

  it("a discard's rows are dropped when a write already on the wire lands while they are read", async () => {
    const { manager, backend } = await openWithBoxes(modelBox(REC, "b1"));
    serveLikeTheApi(backend, REC);
    manager.review.accept("b1");
    const writeHeld = deferred();
    backend.holdWrites = writeHeld.promise;
    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    // Discard lets the queue go; the Accept on the wire may still land.
    const discardRead = deferred();
    backend.holdListings = discardRead.promise;
    backend.log.length = 0;
    const discarding = manager.discardChanges();
    await vi.waitFor(() => expect(backend.log).toContain(`list ${BBOX_RESOURCE}`));
    const saveRead = deferred();
    backend.holdListings = saveRead.promise;
    backend.holdWrites = undefined;
    writeHeld.resolve();
    await vi.waitFor(() =>
      expect(backend.log.filter((call) => call === `list ${BBOX_RESOURCE}`)).toHaveLength(2),
    );
    discardRead.resolve();
    await discarding;

    // The discard's rows were read before the Accept was stored.
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
    saveRead.resolve();
    await saving;
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
  });

  it("a save's rows are dropped when a later save writes while they are read, even landing first", async () => {
    const { manager, backend, seam } = await openWithBoxes(
      modelBox(REC, "b1"),
      modelBox(REC, "b2"),
    );
    serveLikeTheApi(backend, REC);
    manager.review.accept("b1");
    const firstRead = deferred();
    backend.holdListings = firstRead.promise;
    backend.log.length = 0;
    const first = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`list ${BBOX_RESOURCE}`));

    const secondRead = deferred();
    backend.holdListings = secondRead.promise;
    drag(seam, "b2");
    const second = manager.flushSave();
    await vi.waitFor(() =>
      expect(backend.log.filter((call) => call === `list ${BBOX_RESOURCE}`)).toHaveLength(2),
    );
    firstRead.resolve();
    await first;

    // The first save's rows hold b2 as it was before the second save moved it.
    expect(geometryOf(manager, "b2")).toEqual(MOVED);
    expect(statusOf(manager, "b2")).toBe(REVIEW_STATUS.ACCEPTED);
    secondRead.resolve();
    expect(await second).toBe(true);

    // The second save's rows: b2 moved, accepted, and still the model's.
    expect(geometryOf(manager, "b2")).toEqual(MOVED);
    expect(manager.annotations.find("b2")?.review).toMatchObject({
      status: REVIEW_STATUS.ACCEPTED,
      storedStatus: REVIEW_STATUS.ACCEPTED,
      sourceType: "model",
      confidence: 0.87,
    });
    expect(rowOf(manager, "b2")).toMatchObject({
      filterKey: REVIEW_STATUS.ACCEPTED,
      canAccept: false,
    });
  });

  it("rows read before rows already taken are dropped, whatever changed in between", async () => {
    const { manager, backend } = await openWithBoxes(modelBox(REC, "b1"));
    const firstRead = deferred();
    backend.holdListings = firstRead.promise;
    backend.log.length = 0;
    const first = manager.discardChanges();
    await vi.waitFor(() => expect(backend.log).toContain(`list ${BBOX_RESOURCE}`));
    backend.holdListings = undefined;
    // Changed on the server by someone else — no write of this workspace.
    backend.records[REC][BBOX_RESOURCE][0].review_status = "accepted";

    await manager.discardChanges();
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
    firstRead.resolve();
    await first;

    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
  });

  it("a later read still on its way does not stop an earlier one: Discard brings back a box deleted during a save", async () => {
    const { manager, backend, seam } = await openWithBoxes(
      modelBox(REC, "b1"),
      modelBox(REC, "b2"),
      humanBox(REC, "h1"),
    );
    serveLikeTheApi(backend, REC);
    manager.review.accept("b1");
    const writeHeld = deferred();
    backend.holdWrites = writeHeld.promise;
    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    // Deleted while the save writes: queued behind it, not part of it.
    manager.deleteAnnotation(manager.annotations.find("h1")!, "image-widget");
    // The save, written, reads its entities back — slowly.
    const saveEntities = deferred();
    backend.holdEntityListings = saveEntities.promise;
    backend.log.length = 0;
    backend.holdWrites = undefined;
    writeHeld.resolve();
    await vi.waitFor(() => expect(backend.log).toContain("listEntities"));
    backend.holdEntityListings = undefined;

    // Discard is offered now — nothing is saving — and reads the record back.
    expect(manager.saving).toBe(false);
    const discardRows = deferred();
    backend.holdListings = discardRows.promise;
    backend.log.length = 0;
    const discarding = manager.discardChanges();
    await vi.waitFor(() => expect(backend.log).toContain(`list ${BBOX_RESOURCE}`));
    // The save reads its rows back after the discard did.
    const saveRows = deferred();
    backend.holdListings = saveRows.promise;
    saveEntities.resolve();
    await vi.waitFor(() =>
      expect(backend.log.filter((call) => call === `list ${BBOX_RESOURCE}`)).toHaveLength(2),
    );
    drag(seam, "b2");
    discardRows.resolve();
    await discarding;

    // The discard's rows are not older than anything taken: h1 is back at once.
    expect(manager.annotations.find("h1")).toBeDefined();
    saveRows.resolve();
    await saving;
    expect(manager.annotations.find("h1")).toBeDefined();
    expect(geometryOf(manager, "b2")).toEqual(MOVED);
    expect(manager.pendingMutations.map((m) => m.op === "update" && m.id)).toEqual(["b2"]);
  });

  it("a save's read-back takes the rows around work begun during it, rather than being called off", async () => {
    const { manager, backend, seam } = await openWithBoxes(
      modelBox(REC, "b1"),
      modelBox(REC, "b2"),
    );
    // What the server stores for b1 — coordinates of its own, which only a read can show.
    const serverCoords = [0.25, 0.25, 0.2, 0.2];
    backend.onWrite = (write) => {
      if (write.op === "update" && write.id === "b1") {
        Object.assign(backend.records[REC][BBOX_RESOURCE][0], {
          coords: serverCoords,
          review_status: "accepted",
        });
      }
    };
    drag(seam, "b1");
    const read = deferred();
    backend.holdListings = read.promise;
    backend.log.length = 0;
    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`list ${BBOX_RESOURCE}`));
    // Work begun while the rows are read: an edit, and a box waiting for its entity.
    drag(seam, "b2");
    drawDraftAwaitingEntity(seam);
    read.resolve();

    expect(await saving).toBe(false);
    expect(geometryOf(manager, "b1")).toEqual(serverCoords);
    expect(geometryOf(manager, "b2")).toEqual(MOVED);
    expect(statusOf(manager, "b2")).toBe(REVIEW_STATUS.PENDING);
    expect(manager.annotations.find("draft")).toBeDefined();
    expect(manager.pendingMutations.map((m) => m.op === "update" && m.id)).toEqual(["b2"]);
  });

  it("a later save the server refuses calls off no earlier read-back", async () => {
    const { manager, backend } = await openManager(
      { [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1"), modelBox(REC, "b2")] } },
      { entities: [entityOf(REC, "ent-b1"), entityOf(REC, "ent-b2")] },
    );
    const seam = widgetSeam(manager);
    serveLikeTheApi(backend, REC);
    const serve = backend.onWrite!;
    backend.onWrite = (write) => {
      if (write.op === "update" && write.id === "b2") throw refusal("Invalid data");
      serve(write);
    };
    reassignEntity(
      manager.annotations.find("b1")!,
      { mode: "new", entityFields: { category: "zebra" } },
      seam,
    );
    const zebra = manager.annotations.find("b1")!.entityId;
    const firstEntities = deferred();
    backend.holdEntityListings = firstEntities.promise;
    backend.log.length = 0;
    const first = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain("listEntities"));
    // The refused save reads its entities back too; held, so the first's land first.
    const secondEntities = deferred();
    backend.holdEntityListings = secondEntities.promise;

    manager.review.accept("b2");
    const second = manager.flushSave();
    await vi.waitFor(() =>
      expect(backend.log.filter((call) => call === "listEntities")).toHaveLength(2),
    );
    expect(manager.saveError).toContain("Invalid data");
    backend.holdEntityListings = undefined;
    firstEntities.resolve();
    // Not all saved — the refused Accept is still queued — but read back.
    expect(await first).toBe(false);

    // The refused write stored nothing: the first save's entities and rows land.
    expect(manager.entities.map((e) => e.id)).toContain(zebra);
    expect(manager.annotations.find("b1")?.entity).toMatchObject({ category: "zebra" });
    secondEntities.resolve();
    expect(await second).toBe(false);
  });

  it("a later delete the server refuses calls off no earlier read-back, refused as the API module reports it", async () => {
    const { manager, backend } = await openManager(
      { [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1"), humanBox(REC, "h1")] } },
      { entities: [entityOf(REC, "ent-b1"), entityOf(REC, "ent-h1")] },
    );
    const seam = widgetSeam(manager);
    serveLikeTheApi(backend, REC);
    const serve = backend.onWrite!;
    // The dataset is busy as the person's box is deleted: a 409, thrown as the
    // real HTTP module throws it.
    const busy = await refusalOfARealDelete(HTTP_CONFLICT);
    backend.onWrite = (write) => {
      if (write.op === "delete" && write.id === "h1") throw busy;
      return serve(write);
    };
    reassignEntity(
      manager.annotations.find("b1")!,
      { mode: "new", entityFields: { category: "zebra" } },
      seam,
    );
    const zebra = manager.annotations.find("b1")!.entityId;
    const firstEntities = deferred();
    backend.holdEntityListings = firstEntities.promise;
    backend.log.length = 0;
    const first = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain("listEntities"));
    const secondEntities = deferred();
    backend.holdEntityListings = secondEntities.promise;

    manager.deleteAnnotation(manager.annotations.find("h1")!, "image-widget");
    const second = manager.flushSave();
    await vi.waitFor(() =>
      expect(backend.log.filter((call) => call === "listEntities")).toHaveLength(2),
    );
    expect(manager.saveError).toContain("409");
    backend.holdEntityListings = undefined;
    firstEntities.resolve();
    expect(await first).toBe(false);

    // The refused delete stored nothing: the first save's entities and rows land.
    expect(manager.entities.map((e) => e.id)).toContain(zebra);
    expect(manager.annotations.find("b1")?.entity).toMatchObject({ category: "zebra" });
    secondEntities.resolve();
    expect(await second).toBe(false);
  });

  it.each([
    ["its answer lost", new Error("connection reset")],
    ["a proxy's 5xx", GATEWAY_TIMEOUT],
  ])(
    "a later write that may have been stored — %s — calls off an earlier list: the entity it made stays listed",
    async (_failure, lostAnswer) => {
      const { manager, backend } = await openManager(
        { [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1"), modelBox(REC, "b2")] } },
        { entities: [entityOf(REC, "ent-b1"), entityOf(REC, "ent-b2")] },
      );
      const seam = widgetSeam(manager);
      serveLikeTheApi(backend, REC);
      reassignEntity(
        manager.annotations.find("b1")!,
        { mode: "new", entityFields: { category: "zebra" } },
        seam,
      );
      // The first save's entities are read now, and their answer held.
      const firstEntities = deferred();
      backend.holdEntityListings = firstEntities.promise;
      backend.log.length = 0;
      const first = manager.flushSave();
      await vi.waitFor(() => expect(backend.log).toContain("listEntities"));
      backend.holdEntityListings = undefined;

      // A second save creates "lion": the server stores it, and the answer is lost.
      reassignEntity(
        manager.annotations.find("b2")!,
        { mode: "new", entityFields: { category: "lion" } },
        seam,
      );
      const lion = manager.annotations.find("b2")!.entityId;
      backend.loseAnswers = lostAnswer;
      expect(await manager.flushSave()).toBe(false);
      backend.loseAnswers = undefined;
      expect(manager.entities.map((e) => e.id)).toContain(lion);
      firstEntities.resolve();
      await first;

      // The first list was read before "lion" was stored, and is not taken.
      expect(manager.entities.map((e) => e.id)).toContain(lion);
    },
  );

  it("a later save that fails on the way reads the entities back itself, and Discard labels from them", async () => {
    const { manager, backend } = await openManager(
      { [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1"), modelBox(REC, "b2")] } },
      { entities: [entityOf(REC, "ent-b1"), entityOf(REC, "ent-b2")] },
    );
    const seam = widgetSeam(manager);
    serveLikeTheApi(backend, REC);
    reassignEntity(
      manager.annotations.find("b1")!,
      { mode: "new", entityFields: { category: "zebra" } },
      seam,
    );
    const zebra = manager.annotations.find("b1")!.entityId;
    const firstEntities = deferred();
    backend.holdEntityListings = firstEntities.promise;
    backend.log.length = 0;
    const first = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain("listEntities"));
    backend.holdEntityListings = undefined;

    // It may have stored the write before its answer was lost, so it reads
    // the entities back itself (what calling off the first save's list does is
    // the test above's).
    manager.review.accept("b2");
    backend.loseAnswers = new Error("connection reset");
    expect(await manager.flushSave()).toBe(false);
    backend.loseAnswers = undefined;
    firstEntities.resolve();
    await first;

    expect(manager.entities.map((e) => e.id)).toContain(zebra);
    await manager.discardChanges();
    expect(manager.annotations.find("b1")?.entity).toMatchObject({ category: "zebra" });
  });

  it("Discard reads the entities back before the rows, so labels follow the dataset", async () => {
    const { manager, backend } = await openManager(
      { [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1")] } },
      { entities: [entityOf(REC, "ent-b1", { category: "dog" })] },
    );
    // Renamed in the dataset since the record was opened.
    backend.entities[0].category = "wolf";

    await manager.discardChanges();

    expect(manager.annotations.find("b1")?.entity).toMatchObject({ category: "wolf" });
    expect(manager.entities[0]).toMatchObject({ category: "wolf" });
  });

  it("a save that lands after another record was opened reads nothing back", async () => {
    const { manager, backend } = await openManager({
      [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1")] },
      "rec-2": { [BBOX_RESOURCE]: [modelBox("rec-2", "b2")] },
    });
    const held = deferred();
    backend.holdWrites = held.promise;

    manager.review.accept("b1");
    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    await manager.openRecord(DATASET_ID, "rec-2", VIEWPORT);
    backend.log.length = 0;
    backend.holdWrites = undefined;
    held.resolve();

    // That save was record 1's: nothing of record 2 is its to read or report.
    expect(await saving).toBe(false);
    expect(backend.log.filter((call) => call.startsWith("list"))).toEqual([]);
    expect(manager.annotations.find("b2")).toBeDefined();
  });

  it("a reload asked while another record loads does not wipe that record", async () => {
    const { manager, backend } = await openManager({
      [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1")] },
      "rec-2": { [BBOX_RESOURCE]: [modelBox("rec-2", "b2")] },
    });
    const datasetHeld = deferred();
    backend.holdDataset = datasetHeld.promise;
    const opening = manager.openRecord(DATASET_ID, "rec-2", VIEWPORT);

    // Record 2 is named, but its views are not read yet.
    const reloadRead = deferred();
    backend.holdListings = reloadRead.promise;
    const discarding = manager.discardChanges();
    backend.holdListings = undefined;
    backend.holdDataset = undefined;
    datasetHeld.resolve();
    await opening;
    reloadRead.resolve();
    await discarding;

    expect(manager.annotations.find("b2")).toBeDefined();
  });
});
