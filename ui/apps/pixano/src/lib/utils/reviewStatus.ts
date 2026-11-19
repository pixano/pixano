/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  MODEL_SOURCE_TYPE,
  REVIEW_STATUS,
  type ReviewStatus,
} from "$lib/constants/reviewConstants";
import { BaseSchema, WorkspaceType, type Annotation, type Schema } from "$lib/types/dataset";

// The review of a model's annotations, as this app reads it.
//
// A model's annotation arrives `pending`. A person accepts it, as it is or by saving an edit of
// it, or rejects it, which deletes it. The server holds the rules (src/pixano/api/review.py);
// this module only reads a row's status and says which rows a person reviews here. Pure rules,
// no store: the review actions (`reviewActions.ts`) and the components read them.

/**
 * The kinds a person reviews here: those this app draws on an image. The server reviews every
 * entity annotation but tracks, relations and text spans (`is_reviewable_annotation` in
 * src/pixano/schemas/annotations/review.py).
 */
const REVIEWED_KINDS: ReadonlySet<BaseSchema> = new Set([
  BaseSchema.BBox,
  BaseSchema.Mask,
  BaseSchema.Keypoints,
  BaseSchema.MultiPath,
]);

/**
 * The workspaces that draw annotations on a still image; a dataset that names no workspace opens
 * in the image one (`resolveWorkspaceVariant`). A video's frames are not reviewed: the review
 * queue leaves them out (`is_reviewable_view`), so a record whose rows to review were all on
 * frames would never leave it.
 */
const STILL_IMAGE_WORKSPACES: ReadonlySet<WorkspaceType> = new Set([
  WorkspaceType.IMAGE,
  WorkspaceType.IMAGE_VQA,
  WorkspaceType.IMAGE_TEXT_ENTITY_LINKING,
  WorkspaceType.UNDEFINED,
]);

/** The field holding the model's score, for the kinds that have one (`MODEL_SCORE_FIELDS`). */
const MODEL_SCORE_FIELD_BY_KIND: Partial<Record<BaseSchema, string>> = {
  [BaseSchema.BBox]: "confidence",
};

/** A score below this is the server's "not predicted" sentinel (-1), not a score. */
const MIN_MODEL_SCORE = 0;

/** The key of `source_metadata` that names the model its job ran (pixano_worker's `provenance`). */
const METADATA_MODEL_KEY = "model";

/** Whether this app reviews the annotations of a workspace: those drawn on a still image. */
export function isReviewedWorkspace(workspace: WorkspaceType): boolean {
  return STILL_IMAGE_WORKSPACES.has(workspace);
}

/**
 * Whether a person reviews this annotation here: a model's row, of a kind drawn on a still image.
 * A person's annotation has nothing to review.
 */
export function isReviewedHere(annotation: Annotation): boolean {
  return (
    annotation.data.source_type === MODEL_SOURCE_TYPE &&
    REVIEWED_KINDS.has(annotation.table_info.base_schema) &&
    isReviewedWorkspace(annotation.ui.datasetItemType)
  );
}

/**
 * Where a model's row stands with its reviewer, as the screen shows it: an Accept not saved yet
 * included. A model's row stored without a status reads `pending`, as the server reads it
 * (`NOT_REVIEWED_STATUSES` in src/pixano/schemas/annotations/review.py).
 *
 * @returns The status, or null for a row not reviewed here (`isReviewedHere`).
 */
export function reviewStatusOf(annotation: Annotation): ReviewStatus | null {
  if (!isReviewedHere(annotation)) return null;
  if (annotation.ui.unsavedAccept || annotation.data.review_status === REVIEW_STATUS.ACCEPTED) {
    return REVIEW_STATUS.ACCEPTED;
  }
  return REVIEW_STATUS.PENDING;
}

/** Whether the annotation is still to review: a model's row reviewed here, not accepted. */
export function isPendingReview(annotation: Annotation): boolean {
  return reviewStatusOf(annotation) === REVIEW_STATUS.PENDING;
}

/** The annotations still to review, in the order given. */
export function pendingReviewOf(annotations: readonly Annotation[]): Annotation[] {
  return annotations.filter(isPendingReview);
}

/**
 * Whether an update of this row carries an Accept: one taken here and not saved yet. A status
 * read from the row is never sent back: the server would read it as a decision of the user.
 */
export function carriesUnsavedAccept(schema: Schema): boolean {
  if (!REVIEWED_KINDS.has(schema.table_info.base_schema)) return false;
  const annotation = schema as Annotation;
  return annotation.ui.unsavedAccept === true && isReviewedHere(annotation);
}

function parsedMetadata(raw: unknown): Record<string, unknown> {
  if (raw !== null && typeof raw === "object") return raw as Record<string, unknown>;
  if (typeof raw !== "string" || raw === "") return {};
  try {
    const parsed: unknown = JSON.parse(raw);
    return parsed !== null && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

/**
 * The model that proposed the row: the one its job ran, from `source_metadata`, else the source's
 * name, which the worker sets to the job's kind. Null when the row names neither.
 */
export function proposingModelOf(annotation: Annotation): string | null {
  const model = parsedMetadata(annotation.data.source_metadata)[METADATA_MODEL_KEY];
  if (typeof model === "string" && model !== "") return model;
  const sourceName = annotation.data.source_name;
  return typeof sourceName === "string" && sourceName !== "" ? sourceName : null;
}

/** The score the model gave the row, when its kind has one and the model gave it. */
export function modelScoreOf(annotation: Annotation): number | null {
  const field = MODEL_SCORE_FIELD_BY_KIND[annotation.table_info.base_schema];
  if (!field) return null;
  const score = annotation.data[field];
  return typeof score === "number" && Number.isFinite(score) && score >= MIN_MODEL_SCORE
    ? score
    : null;
}

/**
 * The annotations still to review of the objects showing all theirs. An object one of whose
 * annotations to review is hidden, by its eye or by a filter, waits whole: the confidence filter
 * hides a box but not its mask, which would otherwise be accepted without a look at what it
 * outlines.
 */
export function shownPendingReviewOf(annotations: readonly Annotation[]): Annotation[] {
  const pending = pendingReviewOf(annotations);
  const objectsWithAHiddenOne = new Set(
    pending
      .filter((annotation) => annotation.ui.displayControl.hidden)
      .map((annotation) => annotation.data.entity_id),
  );
  return pending.filter((annotation) => !objectsWithAHiddenOne.has(annotation.data.entity_id));
}

/** What the review shows of one annotation, or of the annotations of an object. */
export interface ReviewSummary {
  /** Pending while one of them is still to review; accepted once all are. */
  status: ReviewStatus;
  /** How many are still to review. */
  pendingCount: number;
  /** How many of those are hidden, by their eye or by a filter. */
  hiddenCount: number;
  /** Whether one of them was accepted here and is not saved yet. */
  unsaved: boolean;
  /** The model that proposed the one described: the first scored, among those to review if any. */
  model: string | null;
  /** That one's score, from the same annotation as the model. */
  score: number | null;
}

/**
 * What the review shows of these annotations: one annotation, or the annotations of an object.
 * The model and the score are those of one annotation, the first with a score — an object's box
 * rather than its mask — so that the chip never pairs one model's name with another's score.
 *
 * @returns The summary, or null when none of them is reviewed here.
 */
export function reviewSummaryOf(annotations: readonly Annotation[]): ReviewSummary | null {
  const reviewed = annotations.filter(isReviewedHere);
  if (reviewed.length === 0) return null;
  const pending = reviewed.filter(isPendingReview);
  const described = pending.length > 0 ? pending : reviewed;
  const lead = described.find((annotation) => modelScoreOf(annotation) !== null) ?? described[0];
  return {
    status: pending.length > 0 ? REVIEW_STATUS.PENDING : REVIEW_STATUS.ACCEPTED,
    pendingCount: pending.length,
    hiddenCount: pending.filter((annotation) => annotation.ui.displayControl.hidden).length,
    unsaved: reviewed.some((annotation) => annotation.ui.unsavedAccept === true),
    model: proposingModelOf(lead),
    score: modelScoreOf(lead),
  };
}
