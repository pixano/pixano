/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  drag,
  entityOf,
  MODEL_METADATA,
  modelBox,
  MOVED,
  openManager,
  openWithBoxes,
  REC,
  serveLikeTheApi,
  statusOf,
  STORED,
  updatesSent,
  viewIdOf,
  widgetSeam,
  type Row,
} from "./workspaceHarness.js";
import type { BBoxGeometry } from "$lib/annotations/annotationCollection.svelte.js";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import { CLASSIFICATION_RESOURCE } from "$lib/annotations/kinds/2d/classification/classificationPayloadBuilder.js";
import { beginEntityReassign, reassignEntity } from "$lib/annotations/payloadBuilders.js";
import { REVIEW_STATUS } from "$lib/annotations/reviewStatus.js";

// What an edit of a model's annotation does to its review, run through the real
// workspace — manager, mutation queue, commit helpers — and asserted on what
// the screen shows and on what reaches the backend when the person presses
// Save. What a save does with work begun during it is in
// saveScenarios.svelte.test.ts.

describe("An edit leaves the row in review until it is saved", () => {
  it("an edit reads pending, and Save stores it accepted", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    serveLikeTheApi(backend, REC);

    drag(seam, "b1");
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
    backend.log.length = 0;
    expect(await manager.flushSave()).toBe(true);

    // Saving the edit is the person's choice to keep the row: the server stores it accepted,
    // keeping the model's provenance and score.
    expect(backend.records[REC][BBOX_RESOURCE][0]).toMatchObject({
      coords: MOVED,
      review_status: "accepted",
      source_type: "model",
      confidence: 0.87,
    });
    // The row reads so without the annotations being read back.
    expect(backend.log).not.toContain(`list ${BBOX_RESOURCE}`);
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
  });

  it("moving a model's box to another entity reads pending until saved", async () => {
    const { manager, backend } = await openManager(
      { [REC]: { [BBOX_RESOURCE]: [modelBox(REC, "b1")] } },
      { entities: [entityOf(REC, "ent-b1"), entityOf(REC, "ent-x")] },
    );

    reassignEntity(
      manager.annotations.find("b1")!,
      { mode: "existing", entityId: "ent-x" },
      widgetSeam(manager),
    );

    // Unsaved, the reassignment leaves the row in review; saved, it reads accepted.
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
    await manager.flushSave();
    const updates = updatesSent(backend);
    expect(updates).toHaveLength(1);
    expect(updates[0]).toMatchObject({ id: "b1", body: { entity_id: "ent-x" } });
    expect(updates[0].op === "update" && updates[0].body).not.toHaveProperty("review_status");
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.ACCEPTED);
  });

  it("a save that fails leaves the status as stored", async () => {
    const { manager, backend, seam } = await openWithBoxes(modelBox(REC, "b1"));
    backend.failWrites = new Error("backend down");

    drag(seam, "b1");
    expect(await manager.flushSave()).toBe(false);

    // The edit is unsaved again: the row reads pending.
    expect(statusOf(manager, "b1")).toBe(REVIEW_STATUS.PENDING);
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
    expect(manager.annotations.find("c1")?.review?.confidence).toBe(0.87);

    beginEntityReassign(manager.annotations.find("c1")!, seam, { label: "classification" });
    manager.confirmPendingAnnotation({ mode: "existing", entityId: "ent-cat" });

    // The interface rewrites the score as a person's, but the score is the
    // model's: the server ignores it, so nothing changed and nothing is sent.
    expect(manager.pendingCount).toBe(0);
    expect(statusOf(manager, "c1")).toBe(REVIEW_STATUS.PENDING);
  });
});
