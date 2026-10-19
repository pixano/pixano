/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import {
  deferred,
  drag,
  geometryOf,
  humanBox,
  MOVED,
  openWithBoxes,
  REC,
  serveLikeTheApi,
  STORED,
  updatesSent,
  type FakeBackend,
} from "./workspaceHarness.js";
import type { BBoxGeometry } from "$lib/annotations/annotationCollection.svelte.js";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import { commitNewAnnotation } from "$lib/annotations/payloadBuilders.js";

// What a save does with the work around it, run through the real workspace —
// manager, mutation queue, record loader, commit helpers — over a recording
// fake backend: work begun while a request is on the wire.

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
});
