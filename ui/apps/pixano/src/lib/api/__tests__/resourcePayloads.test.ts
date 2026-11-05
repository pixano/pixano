/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { toRawAnnotation } from "../adapters";
import { normalizeTableName } from "../resourceNames";
import { toAcceptMutation, toResourceMutation, type ResourceMutation } from "../resourcePayloads";
import type { RecordComponentResponse } from "../restTypes";
import { Annotation, BBox } from "$lib/types/dataset";

/** A model's box as the API returns it, already accepted. */
const READ_BACK = {
  id: "box-1",
  record_id: "record-1",
  view_id: "view-1",
  entity_id: "entity-1",
  coords: [0.1, 0.1, 0.2, 0.2],
  format: "xywh",
  is_normalized: true,
  confidence: 0.8,
  source_type: "model",
  source_name: "detection",
  source_metadata: '{"model": "yolo26n"}',
  review_status: "accepted",
  created_at: "",
  updated_at: "",
} as unknown as RecordComponentResponse;

describe("a legacy edit of an annotation", () => {
  it("does not send back the review status it read", () => {
    // The legacy app sent back the status it had read with every edit, and the server reads a
    // status sent as a decision of the user.
    const box = new BBox(toRawAnnotation(READ_BACK, new Map([["view-1", "image"]]), "bboxes"));
    box.data.coords = [0.3, 0.3, 0.2, 0.2];

    const body = toResourceMutation("update", box).body ?? {};

    expect(body).not.toHaveProperty("review_status");
    expect(body.coords).toEqual([0.3, 0.3, 0.2, 0.2]);
  });
});

/** What every model's row carries, whatever its kind: its provenance and a review status. */
const MODEL_PROVENANCE = {
  record_id: "record-1",
  view_id: "view-1",
  entity_id: "entity-1",
  source_type: "model",
  source_name: "detection",
  source_metadata: '{"model": "yolo26n"}',
  created_at: "",
  updated_at: "",
};

/** A model's row of each resource the legacy app writes, with the fields of its kind. */
const MODEL_ROWS: Record<string, Record<string, unknown>> = {
  bboxes: { coords: [0.1, 0.1, 0.2, 0.2], format: "xywh", is_normalized: true, confidence: 0.8 },
  masks: { size: [2, 2], counts: "04" },
  "multi-paths": { coords: [0, 0, 1, 1], num_points: [2], is_closed: false },
  keypoints: { template_id: "face", coords: [0.5, 0.5], states: ["visible"] },
  "text-spans": { spans_start: [0], spans_end: [4], mention: "word" },
  tracklets: { start_timestep: 0, end_timestep: 3 },
};

/** The legacy workspace's own reading of a row: the adapter, then the typed annotation. */
function readAsTheWorkspaceDoes(resource: string, reviewStatus: string): Annotation {
  const table = normalizeTableName(resource);
  const row = {
    id: `${table}-1`,
    ...MODEL_PROVENANCE,
    ...MODEL_ROWS[resource],
    review_status: reviewStatus,
  } as RecordComponentResponse;
  const raw = toRawAnnotation(row, new Map([["view-1", "image"]]), table);
  return Annotation.deepCreateInstanceArray({ [table]: [raw] })[table][0];
}

describe("every annotation the legacy app writes", () => {
  // Every serializer sent back the status it had read. The server's review rules would refuse,
  // with a 400 that blocks the save queue, the second edit of a model's row stored with no status
  // ("cannot be emptied" once the first edit had accepted it), and the split of any model
  // tracklet with a status (its clone is a person's row, which takes no status).
  const cases = Object.keys(MODEL_ROWS).flatMap((resource) =>
    (["update", "create"] as ResourceMutation["op"][]).flatMap((op) =>
      ["", "pending", "accepted"].map((status) => ({ resource, op, status })),
    ),
  );

  it.each(cases)(
    "leaves out the review status: $op of a model's $resource read as $status",
    ({ resource, op, status }) => {
      const annotation = readAsTheWorkspaceDoes(resource, status);

      const mutation = toResourceMutation(op, annotation);

      expect(mutation.target.resource).toBe(resource);
      expect(mutation.body).toBeDefined();
      expect(mutation.body).not.toHaveProperty("review_status");
    },
  );
});

describe("an Accept taken here", () => {
  // The one status the legacy app sends: a decision of its user, taken on a model's row in
  // review and not saved yet. It rides on the row's update, with whatever else the row holds.
  const REVIEWED = ["bboxes", "masks", "multi-paths", "keypoints"];

  it.each(REVIEWED)("rides on the update of a model's %s", (resource) => {
    const annotation = readAsTheWorkspaceDoes(resource, "pending");
    annotation.ui.unsavedAccept = true;

    const mutation = toResourceMutation("update", annotation);

    expect(mutation.body).toMatchObject({ review_status: "accepted" });
  });

  it("rides with an edit of the row", () => {
    const box = new BBox(toRawAnnotation(READ_BACK, new Map([["view-1", "image"]]), "bboxes"));
    box.data.review_status = "pending";
    box.data.coords = [0.3, 0.3, 0.2, 0.2];
    box.ui.unsavedAccept = true;

    const body = toResourceMutation("update", box).body ?? {};

    expect(body).toMatchObject({ review_status: "accepted", coords: [0.3, 0.3, 0.2, 0.2] });
  });

  it("never rides on a create: this app creates a person's rows, which take no status", () => {
    const annotation = readAsTheWorkspaceDoes("bboxes", "pending");
    annotation.ui.unsavedAccept = true;

    expect(toResourceMutation("create", annotation).body).not.toHaveProperty("review_status");
  });

  it.each(["text-spans", "tracklets"])(
    "never rides on a %s, which no one reviews yet",
    (resource) => {
      const annotation = readAsTheWorkspaceDoes(resource, "pending");
      annotation.ui.unsavedAccept = true;

      expect(toResourceMutation("update", annotation).body).not.toHaveProperty("review_status");
    },
  );
});

describe("an Accept taken alone", () => {
  it("sends the status and nothing else, so that the row is stored as the model wrote it", () => {
    const annotation = readAsTheWorkspaceDoes("masks", "pending");

    expect(toAcceptMutation(annotation)).toEqual({
      op: "update",
      target: { resource: "masks", id: annotation.id },
      body: { review_status: "accepted" },
      table: annotation.table_info.name,
    });
  });
});
