/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import type { WorkspaceManager } from "../workspaceManager.svelte.js";
import { deferred, modelBox, openManager, VIEWPORT, widgetSeam } from "./workspaceHarness.js";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import { BBox3DSession } from "$lib/annotations/kinds/3d/bbox3d/bbox3dSession.svelte.js";
import { beginEntityReassign } from "$lib/annotations/payloadBuilders.js";
import type { Rotation3x3 } from "$lib/annotations/types.js";

// The record's one unsaved count, through the real manager, queue, seam and
// tools — only HTTP is faked. What it must hold: wherever "Save & next" refuses
// to move, the count the Review tab and every widget toolbar show is not zero.

const REC_1 = "rec-1";
const REC_2 = "rec-2";

const IDENTITY: Rotation3x3 = [1, 0, 0, 0, 1, 0, 0, 0, 1];
const NEW_BOX: [number, number, number, number, number, number] = [0, 0, 0, 1, 1, 1];

function twoRecords() {
  return {
    [REC_1]: { [BBOX_RESOURCE]: [modelBox(REC_1, "b1")] },
    [REC_2]: { [BBOX_RESOURCE]: [modelBox(REC_2, "b2")] },
  };
}

/** Two records holding a model's box, the first open in the real workspace. */
async function onTheRecord() {
  return openManager(twoRecords(), { next: { recordId: REC_2, remaining: 1 } });
}

/** The count both counters read — asserted equal, so a test on one is a test on both. */
function unsavedCount(manager: WorkspaceManager): number {
  expect(manager.review.unsavedCount).toBe(manager.unsavedCount);
  return manager.unsavedCount;
}

/** Run "Save & next" and say whether it stayed on the record, refusing to move. */
async function saveAndNextStays(manager: WorkspaceManager): Promise<boolean> {
  await manager.review.saveAndNext(VIEWPORT);
  return manager.recordId === REC_1 && manager.review.outcome?.kind === "not-saved";
}

describe("The record's unsaved count", () => {
  it("counts each raised holder of staged work once, nothing queued", async () => {
    const { manager } = await onTheRecord();
    const hud = widgetSeam(manager, "point-cloud-widget").claimStagedWork!(() => {});
    const image = widgetSeam(manager);
    const polygon = image.claimStagedWork!(() => {});
    const resize = image.claimStagedWork!(() => {});

    hud.set(true);
    polygon.set(true);
    resize.set(true);
    expect(manager.pendingCount).toBe(0);
    expect(unsavedCount(manager)).toBe(3);

    expect(await saveAndNextStays(manager)).toBe(true);
    expect(unsavedCount(manager)).toBe(3);

    resize.set(false);
    expect(unsavedCount(manager)).toBe(2);
    image.releaseStagedWork!();
    expect(unsavedCount(manager)).toBe(1);
  });

  it("adds a holder's work to the annotations a change is queued for", async () => {
    const { manager } = await onTheRecord();
    manager.review.accept("b1");
    // A shape begun on the canvas: in no change yet, so counted on its own.
    widgetSeam(manager).claimStagedWork!(() => {}).set(true);

    expect(unsavedCount(manager)).toBe(2);
  });

  it("counts a new 3D box once through its whole life: in the HUD, waiting for its entity, queued", async () => {
    const { manager } = await onTheRecord();
    const hud = new BBox3DSession(widgetSeam(manager, "point-cloud-widget"));
    hud.setResetEditor(() => {});

    // Held in the HUD: "Apply this 3D box?" not answered yet.
    hud.reportReady(NEW_BOX, IDENTITY);
    expect(unsavedCount(manager)).toBe(1);
    expect(await saveAndNextStays(manager)).toBe(true);
    expect(unsavedCount(manager)).toBe(1);

    // Applied from the HUD: a draft, waiting for its entity in the form. The
    // form is the draft's: one item, not two.
    hud.save();
    expect(manager.pendingAnnotation).not.toBeNull();
    expect(manager.pendingCount).toBe(0);
    expect(unsavedCount(manager)).toBe(1);
    expect(await saveAndNextStays(manager)).toBe(true);
    expect(unsavedCount(manager)).toBe(1);

    // Its entity chosen: an entity and the box, two writes for one annotation.
    manager.confirmPendingAnnotation({ mode: "new", entityFields: { category: "car" } });
    expect(manager.pendingCount).toBe(2);
    expect(unsavedCount(manager)).toBe(1);

    await manager.review.saveAndNext(VIEWPORT);
    expect(manager.recordId).toBe(REC_2);
    expect(unsavedCount(manager)).toBe(0);
  });

  it("counts the entity form open on a stored annotation's reassignment", async () => {
    const { manager } = await onTheRecord();
    const seam = widgetSeam(manager);

    beginEntityReassign(manager.annotations.find("b1")!, seam, { label: "box entity" });
    expect(manager.pendingCount).toBe(0);
    expect(unsavedCount(manager)).toBe(1);
    expect(await saveAndNextStays(manager)).toBe(true);
    expect(unsavedCount(manager)).toBe(1);

    manager.cancelPendingAnnotation();
    expect(unsavedCount(manager)).toBe(0);
  });

  it("counts a change on the wire until it is stored", async () => {
    const { manager, backend } = await onTheRecord();
    const held = deferred();
    backend.holdWrites = held.promise;
    manager.review.accept("b1");

    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    // The decision left the queue with its request: still not stored.
    expect(manager.pendingMutations).toEqual([]);
    expect(unsavedCount(manager)).toBe(1);
    expect(await saveAndNextStays(manager)).toBe(true);
    expect(unsavedCount(manager)).toBe(1);

    held.resolve();
    expect(await saving).toBe(true);
    expect(unsavedCount(manager)).toBe(0);
  });
});
