/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import type { WorkspaceManager } from "../workspaceManager.svelte.js";
import { deferred, modelBox, openManager, widgetSeam } from "./workspaceHarness.js";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import { beginEntityReassign } from "$lib/annotations/payloadBuilders.js";

// The record's one unsaved count, through the real manager, queue, seam and
// tools — only HTTP is faked. What it must hold: wherever a save reports work
// left, the count the review controller and every widget toolbar show is not
// zero.

const REC_1 = "rec-1";

/** A record holding a model's box, open in the real workspace. */
async function onTheRecord() {
  return openManager({ [REC_1]: { [BBOX_RESOURCE]: [modelBox(REC_1, "b1")] } });
}

/** The count both counters read — asserted equal, so a test on one is a test on both. */
function unsavedCount(manager: WorkspaceManager): number {
  expect(manager.review.unsavedCount).toBe(manager.unsavedCount);
  return manager.unsavedCount;
}

describe("The record's unsaved count", () => {
  it("counts each raised holder of staged work once, nothing queued", async () => {
    const { manager } = await onTheRecord();
    const pointCloud = widgetSeam(manager, "point-cloud-widget").claimStagedWork!(() => {});
    const image = widgetSeam(manager);
    const polygon = image.claimStagedWork!(() => {});
    const resize = image.claimStagedWork!(() => {});

    pointCloud.set(true);
    polygon.set(true);
    resize.set(true);
    expect(manager.pendingCount).toBe(0);
    expect(unsavedCount(manager)).toBe(3);

    expect(await manager.flushSave()).toBe(false);
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

  it("counts the entity form open on a stored annotation's reassignment", async () => {
    const { manager } = await onTheRecord();
    const seam = widgetSeam(manager);

    beginEntityReassign(manager.annotations.find("b1")!, seam, { label: "box entity" });
    expect(manager.pendingCount).toBe(0);
    expect(unsavedCount(manager)).toBe(1);
    expect(await manager.flushSave()).toBe(false);
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

    held.resolve();
    expect(await saving).toBe(true);
    expect(unsavedCount(manager)).toBe(0);
  });
});
