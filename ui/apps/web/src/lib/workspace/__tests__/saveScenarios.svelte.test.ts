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
  MOVED,
  openManager,
  openWithBoxes,
  REC,
  refusal,
  serveLikeTheApi,
  STORED,
  updatesSent,
  VIEWPORT,
  widgetSeam,
  type FakeBackend,
} from "./workspaceHarness.js";
import type { BBoxGeometry } from "$lib/annotations/annotationCollection.svelte.js";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import { commitNewAnnotation, reassignEntity } from "$lib/annotations/payloadBuilders.js";
import { ApiError } from "$lib/api/apiClient.js";

// What a save does with the work around it, run through the real workspace —
// manager, mutation queue, record loader, commit helpers — over a recording
// fake backend: work begun while a request is on the wire, and the entities a
// save creates.

/** A 5xx a proxy answers after the server stored the write: no refusal, so it may have been stored. */
const GATEWAY_TIMEOUT = new ApiError("Gateway Timeout", 504, "");

/** Where a first drag puts a box, before one to `MOVED`. */
const DRAGGED_FIRST: BBoxGeometry = [0.2, 0.2, 0.2, 0.2];
/** Where a last drag puts a box, after one to `MOVED`. */
const DRAGGED_LAST: BBoxGeometry = [0.5, 0.5, 0.2, 0.2];

describe("Work begun while a save is on the wire", () => {
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
