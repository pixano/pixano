/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import type { LocalAnnotation } from "../annotationCollection.svelte.js";
import {
  HUMAN_REVIEW_FILTER,
  isReviewable,
  isShownByReviewFilter,
  REVIEW_STATUS,
  reviewFilterKeyOf,
  reviewOf,
  storedStatusAfterWrite,
  type AnnotationReview,
  type ReviewStatus,
} from "../reviewStatus.js";

const MODEL_ROW = {
  source_type: "model",
  source_name: "detection",
  source_metadata: JSON.stringify({
    job_id: "j",
    kind: "detection",
    model: "yolo",
    model_version: "v8",
  }),
  review_status: "pending",
  confidence: 0.42,
};

/** The score column a box's loader declares (`PersistedAnnotationFields.scoreFields`). */
const OWN_SCORE = ["confidence"];

/** A model's row of a kind scoring each label, with the scores given. */
function perLabelRow(confidences: unknown) {
  return { ...MODEL_ROW, confidence: undefined, confidences };
}

function annotation(
  id: string,
  review: AnnotationReview | undefined,
  persisted = true,
): LocalAnnotation {
  return {
    id,
    entityId: `ent-${id}`,
    kind: "bbox",
    viewId: "v",
    geometry: [0, 0, 1, 1],
    persisted,
    review,
  };
}

const modelReview = (status: ReviewStatus): AnnotationReview => ({
  ...reviewOf(MODEL_ROW),
  status,
});

describe("reviewOf", () => {
  it("reads a model's row: status, provenance, model and score", () => {
    expect(reviewOf(MODEL_ROW, OWN_SCORE)).toEqual({
      status: "pending",
      sourceType: "model",
      sourceName: "detection",
      model: "yolo",
      modelVersion: "v8",
      confidence: 0.42,
      scoreFields: OWN_SCORE,
    });
  });

  it("reads a model's accepted row as accepted", () => {
    expect(reviewOf({ ...MODEL_ROW, review_status: "accepted" }).status).toBe("accepted");
  });

  it("reads a person's row as having no status", () => {
    expect(
      reviewOf({
        source_type: "other",
        source_name: "Pixano",
        source_metadata: "{}",
        review_status: "",
      }),
    ).toMatchObject({ status: "", sourceType: "other", model: undefined });
  });

  it("reads a model's row with no status as pending, as the server does", () => {
    expect(reviewOf({ ...MODEL_ROW, review_status: "" }).status).toBe("pending");
    expect(reviewOf({ ...MODEL_ROW, review_status: undefined }).status).toBe("pending");
  });

  it("never throws on malformed or missing provenance", () => {
    for (const source_metadata of ["{not json", "[1, 2]", "42", "null", undefined]) {
      const review = reviewOf({ ...MODEL_ROW, source_metadata });
      expect(review.model).toBeUndefined();
      expect(review.status).toBe("pending");
    }
    expect(reviewOf({})).toEqual({
      status: "",
      sourceType: "",
      sourceName: "",
      model: undefined,
      modelVersion: undefined,
      confidence: undefined,
      scoreFields: [],
    });
  });

  it("drops the 'not predicted' score sentinel", () => {
    expect(reviewOf({ ...MODEL_ROW, confidence: -1 }, OWN_SCORE).confidence).toBeUndefined();
  });

  it("reads the score of a schema that gives one per label", () => {
    const perLabel = ["confidences"];
    expect(reviewOf(perLabelRow([0.87, 0.1]), perLabel).confidence).toBe(0.87);
    // The first score the model actually gave.
    expect(reviewOf(perLabelRow([-1, 0.6]), perLabel).confidence).toBe(0.6);
    expect(reviewOf(perLabelRow("0.9"), perLabel).confidence).toBeUndefined();
  });

  it("reads the score columns the kind declares, in its order, and no other", () => {
    const both = { ...perLabelRow([0.1]), confidence: 0.42 };
    expect(reviewOf(both, ["confidence", "confidences"]).confidence).toBe(0.42);
    expect(reviewOf(both, ["confidences", "confidence"]).confidence).toBe(0.1);
    // A column this module has never heard of: the kind's declaration is enough.
    const scored = { ...MODEL_ROW, scores: [0.3] };
    expect(reviewOf(scored, ["scores"]).confidence).toBe(0.3);
    // A kind that declares no score has none, whatever its row holds.
    expect(reviewOf(MODEL_ROW).confidence).toBeUndefined();
  });
});

describe("isReviewable", () => {
  it("is true for a stored model's annotation only", () => {
    expect(isReviewable(annotation("m", modelReview("pending")))).toBe(true);
    expect(isReviewable(annotation("a", modelReview("accepted")))).toBe(true);
    expect(isReviewable(annotation("h", reviewOf({ source_type: "other" })))).toBe(false);
    expect(isReviewable(annotation("d", undefined, false))).toBe(false);
    // A draft never is, even one carrying a model's review by mistake.
    expect(isReviewable(annotation("x", modelReview("pending"), false))).toBe(false);
  });
});

describe("reviewFilterKeyOf", () => {
  it("files every annotation under one filter key", () => {
    expect(reviewFilterKeyOf(annotation("p", modelReview("pending")))).toBe("pending");
    expect(reviewFilterKeyOf(annotation("m", modelReview("accepted")))).toBe("accepted");
    expect(reviewFilterKeyOf(annotation("h", reviewOf({ source_type: "human" })))).toBe(
      HUMAN_REVIEW_FILTER,
    );
    expect(reviewFilterKeyOf(annotation("d", undefined, false))).toBe(HUMAN_REVIEW_FILTER);
  });
});

describe("isShownByReviewFilter", () => {
  it("hides what the filter hides, and always shows a draft", () => {
    const hidden = new Set([REVIEW_STATUS.ACCEPTED, HUMAN_REVIEW_FILTER] as const);
    expect(isShownByReviewFilter(annotation("m", modelReview("pending")), hidden)).toBe(true);
    expect(isShownByReviewFilter(annotation("a", modelReview("accepted")), hidden)).toBe(false);
    expect(isShownByReviewFilter(annotation("h", reviewOf({})), hidden)).toBe(false);
    expect(isShownByReviewFilter(annotation("d", undefined, false), hidden)).toBe(true);
    // A draft carrying a model's review by mistake still shows.
    expect(isShownByReviewFilter(annotation("x", modelReview("accepted"), false), hidden)).toBe(
      true,
    );
  });

  it("shows everything when nothing is hidden", () => {
    const nothing = new Set<never>();
    for (const shown of [
      annotation("m", modelReview("pending")),
      annotation("a", modelReview("accepted")),
      annotation("h", reviewOf({})),
    ]) {
      expect(isShownByReviewFilter(shown, nothing)).toBe(true);
    }
  });
});

describe("storedStatusAfterWrite", () => {
  const stored = (status: ReviewStatus): AnnotationReview =>
    reviewOf({ ...MODEL_ROW, review_status: status });

  it("stores an Accept", () => {
    expect(storedStatusAfterWrite(stored("pending"), { review_status: "accepted" })).toBe(
      "accepted",
    );
  });

  it("stores a change to a model's row accepted, whatever the status", () => {
    for (const status of ["pending", "accepted"] as const) {
      expect(storedStatusAfterWrite(stored(status), { coords: [0, 0, 1, 1] })).toBe("accepted");
    }
  });

  it("reads an echo or pending as no decision, as the server does", () => {
    expect(storedStatusAfterWrite(stored("accepted"), { review_status: "accepted" })).toBe(
      "accepted",
    );
    expect(storedStatusAfterWrite(stored("accepted"), { review_status: "pending" })).toBe(
      "accepted",
    );
    expect(storedStatusAfterWrite(stored("pending"), { review_status: "pending" })).toBe("pending");
  });

  it("moves no status on a person's row", () => {
    expect(
      storedStatusAfterWrite(reviewOf({ source_type: "other" }), { coords: [0, 0, 1, 1] }),
    ).toBe("");
  });
});
