/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { toRawAnnotation } from "$lib/api/adapters";
import { normalizeTableName } from "$lib/api/resourceNames";
import type { RecordComponentResponse } from "$lib/api/restTypes";
import { REVIEW_STATUS } from "$lib/constants/reviewConstants";
import { Annotation, BaseSchema, Entity, WorkspaceType } from "$lib/types/dataset";
import {
  carriesUnsavedAccept,
  isPendingReview,
  isReviewedHere,
  isReviewedWorkspace,
  modelScoreOf,
  pendingReviewOf,
  proposingModelOf,
  reviewStatusOf,
  reviewSummaryOf,
  shownPendingReviewOf,
} from "$lib/utils/reviewStatus";

const MODEL = {
  source_type: "model",
  source_name: "detection",
  source_metadata: '{"model": "yolo26n"}',
};
const PERSON = { source_type: "other", source_name: "Pixano", source_metadata: "{}" };

/** The fields of a row of each resource, past its provenance. */
const FIELDS: Record<string, Record<string, unknown>> = {
  bboxes: { coords: [0.1, 0.1, 0.2, 0.2], format: "xywh", is_normalized: true, confidence: 0.8 },
  masks: { size: [2, 2], counts: "04" },
  "multi-paths": { coords: [0, 0, 1, 1], num_points: [2], is_closed: false },
  keypoints: { template_id: "face", coords: [0.5, 0.5], states: ["visible"] },
  "text-spans": { spans_start: [0], spans_end: [4], mention: "word" },
  tracklets: { start_timestep: 0, end_timestep: 3 },
};

/** A row read as the workspace reads it: the adapter, then the typed annotation. */
function read(
  resource: string,
  row: Record<string, unknown> = {},
  workspace: WorkspaceType = WorkspaceType.IMAGE,
): Annotation {
  const table = normalizeTableName(resource);
  const component = {
    id: `${table}-1`,
    record_id: "record-1",
    view_id: "view-1",
    entity_id: "entity-1",
    created_at: "",
    updated_at: "",
    ...MODEL,
    ...FIELDS[resource],
    ...row,
  } as RecordComponentResponse;
  const raw = toRawAnnotation(component, new Map([["view-1", "image"]]), table);
  const annotation = Annotation.deepCreateInstanceArray({ [table]: [raw] })[table][0];
  annotation.ui.datasetItemType = workspace;
  return annotation;
}

describe("which annotations a person reviews here", () => {
  it.each(["bboxes", "masks", "multi-paths", "keypoints"])(
    "a model's %s on an image",
    (resource) => {
      expect(isReviewedHere(read(resource))).toBe(true);
    },
  );

  it.each(["tracklets", "text-spans"])("not a model's %s, which no one reviews yet", (resource) => {
    expect(isReviewedHere(read(resource))).toBe(false);
  });

  it("not a person's annotation, which has nothing to review", () => {
    expect(isReviewedHere(read("bboxes", PERSON))).toBe(false);
    expect(reviewStatusOf(read("bboxes", PERSON))).toBeNull();
  });

  it("not a model's box on a video's frame, which the review queue leaves out", () => {
    expect(isReviewedHere(read("bboxes", {}, WorkspaceType.VIDEO))).toBe(false);
  });

  it.each([
    WorkspaceType.IMAGE_VQA,
    WorkspaceType.IMAGE_TEXT_ENTITY_LINKING,
    WorkspaceType.UNDEFINED,
  ])("a model's box in the %s workspace, which draws on an image", (workspace) => {
    expect(isReviewedHere(read("bboxes", {}, workspace))).toBe(true);
  });
});

describe("where a model's row stands", () => {
  it.each([
    ["", REVIEW_STATUS.PENDING],
    ["pending", REVIEW_STATUS.PENDING],
    ["accepted", REVIEW_STATUS.ACCEPTED],
  ])("stored as %j, it reads %s", (stored, status) => {
    expect(reviewStatusOf(read("bboxes", { review_status: stored }))).toBe(status);
  });

  it("stored with no status at all, it reads pending, as the server reads it", () => {
    expect(reviewStatusOf(read("bboxes"))).toBe(REVIEW_STATUS.PENDING);
  });

  it("accepted here and not saved yet, it reads accepted", () => {
    const box = read("bboxes", { review_status: "pending" });
    box.ui.unsavedAccept = true;

    expect(reviewStatusOf(box)).toBe(REVIEW_STATUS.ACCEPTED);
    expect(isPendingReview(box)).toBe(false);
  });

  it("lists those still to review, in the order given", () => {
    const pending = read("bboxes", { id: "pending", review_status: "pending" });
    const accepted = read("bboxes", { id: "accepted", review_status: "accepted" });
    const person = read("bboxes", { id: "person", ...PERSON });
    const unstored = read("masks", { id: "unstored", review_status: "" });

    expect(pendingReviewOf([pending, accepted, person, unstored]).map((ann) => ann.id)).toEqual([
      "pending",
      "unstored",
    ]);
  });
});

describe("the Accept an update carries", () => {
  it("only one taken here and not saved yet", () => {
    const box = read("bboxes", { review_status: "pending" });
    expect(carriesUnsavedAccept(box)).toBe(false);

    box.ui.unsavedAccept = true;

    expect(carriesUnsavedAccept(box)).toBe(true);
  });

  it("never a status read from the row", () => {
    expect(carriesUnsavedAccept(read("bboxes", { review_status: "accepted" }))).toBe(false);
  });

  it("never on a row not reviewed here", () => {
    const onAFrame = read("bboxes", {}, WorkspaceType.VIDEO);
    onAFrame.ui.unsavedAccept = true;

    expect(carriesUnsavedAccept(onAFrame)).toBe(false);
  });

  it("never on an entity", () => {
    const entity = new Entity({
      id: "entity-1",
      created_at: "",
      updated_at: "",
      table_info: { name: "entities", group: "entities", base_schema: BaseSchema.Entity },
      data: { record_id: "record-1", parent_id: "" },
    });

    expect(carriesUnsavedAccept(entity)).toBe(false);
  });
});

describe("what the review shows of the model", () => {
  it("names the model its job ran", () => {
    expect(proposingModelOf(read("bboxes"))).toBe("yolo26n");
  });

  it("names the job's kind when no model is recorded", () => {
    expect(proposingModelOf(read("bboxes", { source_metadata: "{}" }))).toBe("detection");
    expect(proposingModelOf(read("bboxes", { source_metadata: "not json" }))).toBe("detection");
  });

  it("names nothing when the row names neither", () => {
    expect(proposingModelOf(read("bboxes", { source_metadata: "", source_name: "" }))).toBeNull();
  });

  it("reads the score of a box", () => {
    expect(modelScoreOf(read("bboxes"))).toBe(0.8);
  });

  it("reads no score where the model gave none, or the kind has none", () => {
    expect(modelScoreOf(read("bboxes", { confidence: -1 }))).toBeNull();
    expect(modelScoreOf(read("masks"))).toBeNull();
  });
});

describe("what is shown still to review", () => {
  const hide = (annotation: Annotation): Annotation => {
    annotation.ui.displayControl = { ...annotation.ui.displayControl, hidden: true };
    return annotation;
  };

  it("the annotations still to review of the objects showing all theirs", () => {
    const shown = read("bboxes", { id: "shown", entity_id: "dog", review_status: "pending" });
    const hidden = hide(
      read("bboxes", { id: "hidden", entity_id: "cat", review_status: "pending" }),
    );
    const accepted = read("bboxes", {
      id: "accepted",
      entity_id: "bird",
      review_status: "accepted",
    });

    expect(shownPendingReviewOf([shown, hidden, accepted]).map((ann) => ann.id)).toEqual(["shown"]);
  });

  it("none of an object one of whose annotations to review is hidden", () => {
    // The confidence filter hides a box, not its mask: the mask waits with its box.
    const box = hide(read("bboxes", { id: "box", entity_id: "dog", review_status: "pending" }));
    const mask = read("masks", { id: "mask", entity_id: "dog", review_status: "pending" });

    expect(shownPendingReviewOf([box, mask])).toEqual([]);
  });
});

describe("the workspaces reviewed here", () => {
  it.each([WorkspaceType.IMAGE, WorkspaceType.IMAGE_VQA, WorkspaceType.IMAGE_TEXT_ENTITY_LINKING])(
    "%s, which draws on a still image",
    (workspace) => {
      expect(isReviewedWorkspace(workspace)).toBe(true);
    },
  );

  it.each([WorkspaceType.VIDEO, WorkspaceType.PCL_3D])("not %s", (workspace) => {
    expect(isReviewedWorkspace(workspace)).toBe(false);
  });
});

describe("what the review shows of an object", () => {
  it("nothing when none of its annotations is a model's", () => {
    expect(reviewSummaryOf([read("bboxes", PERSON)])).toBeNull();
    expect(reviewSummaryOf([])).toBeNull();
  });

  it("pending while one is still to review, with how many, and the model and score of one", () => {
    // The box's: a mask has no score, and its model is not the box's.
    const box = read("bboxes", { id: "box", review_status: "pending", confidence: 0.6 });
    const mask = read("masks", { id: "mask", review_status: "pending", source_metadata: "{}" });
    const accepted = read("bboxes", {
      id: "accepted",
      review_status: "accepted",
      confidence: 0.9,
      source_metadata: '{"model": "other"}',
    });

    expect(reviewSummaryOf([accepted, mask, box])).toEqual({
      status: REVIEW_STATUS.PENDING,
      pendingCount: 2,
      hiddenCount: 0,
      unsaved: false,
      model: "yolo26n",
      score: 0.6,
    });
  });

  it("accepted once all are, saying when an Accept is not saved yet", () => {
    const stored = read("bboxes", { id: "stored", review_status: "accepted" });
    const unsaved = read("masks", { id: "unsaved", review_status: "pending" });
    unsaved.ui.unsavedAccept = true;

    expect(reviewSummaryOf([stored, unsaved])).toMatchObject({
      status: REVIEW_STATUS.ACCEPTED,
      pendingCount: 0,
      unsaved: true,
      model: "yolo26n",
      score: 0.8,
    });
  });

  it("counts those still to review that are hidden", () => {
    const box = read("bboxes", { id: "box", review_status: "pending" });
    const mask = read("masks", { id: "mask", review_status: "pending" });
    mask.ui.displayControl = { ...mask.ui.displayControl, hidden: true };

    expect(reviewSummaryOf([box, mask])).toMatchObject({ pendingCount: 2, hiddenCount: 1 });
  });

  it("leaves out a person's annotation of the object", () => {
    const proposed = read("bboxes", { id: "proposed", review_status: "pending" });
    const drawn = read("bboxes", { id: "drawn", ...PERSON, confidence: 1 });

    expect(reviewSummaryOf([drawn, proposed])).toMatchObject({ pendingCount: 1, score: 0.8 });
  });
});
