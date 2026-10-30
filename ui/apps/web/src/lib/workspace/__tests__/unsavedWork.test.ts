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
  humanBox,
  openManager,
  VIEWPORT,
  widgetSeam,
} from "./workspaceHarness.js";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import { beginEntityReassign } from "$lib/annotations/payloadBuilders.js";

// The record's one unsaved count, through the real manager, queue, seam and
// tools — only HTTP is faked. What it must hold: wherever a save reports work
// left, the count every widget toolbar shows is not zero.

const REC_1 = "rec-1";
const REC_2 = "rec-2";

/** A record holding a person's box, open in the real workspace. */
async function onTheRecord() {
  return openManager({ [REC_1]: { [BBOX_RESOURCE]: [humanBox(REC_1, "b1")] } });
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
    expect(manager.unsavedCount).toBe(3);

    expect(await manager.flushSave()).toBe(false);
    expect(manager.unsavedCount).toBe(3);

    resize.set(false);
    expect(manager.unsavedCount).toBe(2);
    image.releaseStagedWork!();
    expect(manager.unsavedCount).toBe(1);
  });

  it("adds a holder's work to the annotations a change is queued for", async () => {
    const { manager } = await onTheRecord();
    drag(widgetSeam(manager), "b1");
    // A shape begun on the canvas: in no change yet, so counted on its own.
    widgetSeam(manager).claimStagedWork!(() => {}).set(true);

    expect(manager.unsavedCount).toBe(2);
  });

  it("counts the entity form open on a stored annotation's reassignment", async () => {
    const { manager } = await onTheRecord();
    const seam = widgetSeam(manager);

    beginEntityReassign(manager.annotations.find("b1")!, seam, { label: "box entity" });
    expect(manager.pendingCount).toBe(0);
    expect(manager.unsavedCount).toBe(1);
    expect(await manager.flushSave()).toBe(false);
    expect(manager.unsavedCount).toBe(1);

    manager.cancelPendingAnnotation();
    expect(manager.unsavedCount).toBe(0);
  });

  it("counts a change on the wire until it is stored", async () => {
    const { manager, backend } = await onTheRecord();
    const held = deferred();
    backend.holdWrites = held.promise;
    drag(widgetSeam(manager), "b1");

    const saving = manager.flushSave();
    await vi.waitFor(() => expect(backend.log).toContain(`update ${BBOX_RESOURCE}`));
    // The edit left the queue with its request: still not stored.
    expect(manager.pendingMutations).toEqual([]);
    expect(manager.unsavedCount).toBe(1);

    held.resolve();
    expect(await saving).toBe(true);
    expect(manager.unsavedCount).toBe(0);
  });
});

describe("Staged work — each holder's own flag", () => {
  it("Discard asks every holder to drop its work, and is offered with nothing queued", async () => {
    const { manager } = await onTheRecord();
    const pointCloud = widgetSeam(manager, "point-cloud-widget");
    const image = widgetSeam(manager);
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
    expect(manager.hasUnsavedWork).toBe(true);
    await manager.discardChanges();

    expect(dropped.sort()).toEqual(["point cloud", "polygon"]);
    expect(manager.hasUnsavedWork).toBe(false);
    expect(await manager.flushSave()).toBe(true);
  });

  it("lets go of every flag once another record is opened", async () => {
    const { manager } = await openManager({ [REC_1]: {}, [REC_2]: {} });
    widgetSeam(manager, "point-cloud-widget").claimStagedWork!(() => {}).set(true);
    widgetSeam(manager).claimStagedWork!(() => {}).set(true);
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
});
