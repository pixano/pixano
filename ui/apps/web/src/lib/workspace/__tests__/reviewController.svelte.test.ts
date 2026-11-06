/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { REVIEW_PANEL_SOURCE_ID } from "../reviewController.svelte.js";
import {
  DATASET_ID,
  humanBox,
  modelBox,
  openManager,
  viewIdOf,
  VIEWPORT,
  widgetSeam,
} from "./workspaceHarness.js";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import { commitGeometryEdit, reassignEntity } from "$lib/annotations/payloadBuilders.js";
import { HUMAN_REVIEW_FILTER, REVIEW_STATUS } from "$lib/annotations/reviewStatus.js";
import type { Scene2DContext, SeamContext } from "$lib/annotations/scene/sceneContext.js";
import { selectTool2D } from "$lib/annotations/scene/selectTool2D.js";

// The review controller through the real manager: its decisions reach the real
// queue, its Save and Discard go through the real flush and the real loader.
// Only the HTTP edge is fake, and it records.

const REC_1 = "rec-1";
const REC_2 = "rec-2";

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
      canReject: true,
    });
    // An accepted row can still be rejected, which deletes it.
    expect(manager.review.rows[1]).toMatchObject({
      filterKey: REVIEW_STATUS.ACCEPTED,
      canAccept: false,
      canReject: true,
    });
    // A person's row takes no decision.
    expect(manager.review.rows[2]).toMatchObject({
      filterKey: HUMAN_REVIEW_FILTER,
      source: "",
      canAccept: false,
      canReject: false,
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
