/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { LocalAnnotation } from "./annotationCollection.svelte.js";
import type { EntityAnnotationColumns } from "$lib/api/annotations.js";

/**
 * Where a model's annotation stands with its reviewer — the values of the
 * backend's `ReviewStatus` (src/pixano/schemas/annotations/entity_annotation.py).
 *
 * This module holds the vocabulary and the pure rules only, and imports nothing
 * but types: seed loaders and the shared label renderer read it, and a module a
 * kind can reach must never import a registry back (the cycle
 * `viewScopedSeedLoader.ts` explains). The Accept that writes a status goes
 * through the mutation queue, so it lives in `payloadBuilders.ts`
 * (`commitAccept`), with the reject, which deletes the row
 * (`deleteLocalAnnotation`).
 *
 * No display text here: each place that shows a status writes its own words.
 */
export const REVIEW_STATUS = {
  PENDING: "pending",
  ACCEPTED: "accepted",
} as const;

export type ReviewStatus = (typeof REVIEW_STATUS)[keyof typeof REVIEW_STATUS];

/** Every status, in the order a reviewer meets them. */
export const REVIEW_STATUSES: readonly ReviewStatus[] = [
  REVIEW_STATUS.PENDING,
  REVIEW_STATUS.ACCEPTED,
];

/**
 * The column an Accept writes, and the only key of the update body of an
 * Accept taken alone.
 */
export const REVIEW_STATUS_FIELD = "review_status";

/** The `source_type` of a row a model produced — the only rows that are reviewed. */
export const MODEL_SOURCE_TYPE = "model";

/**
 * Filter key of the annotations no model produced. They carry no status, but a
 * reviewer still wants to hide them, or see only them, like any status.
 */
export const HUMAN_REVIEW_FILTER = "human";

/** What a status chip filters on: a model row's status, or "made by a person". */
export type ReviewFilterKey = ReviewStatus | typeof HUMAN_REVIEW_FILTER;

/** Every filter key, in the order the chips show them. */
export const REVIEW_FILTER_KEYS: readonly ReviewFilterKey[] = [
  ...REVIEW_STATUSES,
  HUMAN_REVIEW_FILTER,
];

/**
 * The review state of a persisted annotation, read once from its row. Present
 * on every annotation a seed loader produced (`persistedAnnotation`), absent on
 * a draft: a draft is a person's work, and it gets its row's review state the
 * next time the record is read.
 */
export interface AnnotationReview {
  /**
   * A model row's status as the screen shows it: an unsaved Accept included; an
   * unsaved edit leaves it as stored. Empty on a row no model produced.
   */
  status: ReviewStatus | "";
  /**
   * The status the dataset holds for the row — what Discard puts back, and
   * what tells an unsaved Accept from a stored one. Read with the row, then
   * moved only by a write of it (`AnnotationCollection.recordWrite`), never by
   * an Accept still unsaved. Absent on a review built by hand rather than read
   * from a row: `status` is then what is stored (`storedStatusOf`).
   */
  storedStatus?: ReviewStatus | "";
  sourceType: string;
  sourceName: string;
  /** The model's name, from `source_metadata`, when the worker recorded it. */
  model?: string;
  modelVersion?: string;
  /** The model's score, when the kind has one and the model gave it. */
  confidence?: number;
  /**
   * The columns of the row that hold the model's score, as the kind's seed
   * loader declares them (`persistedAnnotation`). Only the model writes them:
   * the server keeps them through a person's edit of a model's row and does not
   * take a change to them for an edit, so the interface ignores them too
   * when it asks whether an edit changes anything. Empty, or absent on a review
   * built by hand, for a kind with no score.
   */
  scoreFields?: readonly string[];
}

/** A reviewable annotation: one whose `review` is known to carry a model's status. */
export type ReviewableAnnotation = LocalAnnotation & {
  review: AnnotationReview & { status: ReviewStatus };
};

const KNOWN_STATUSES: ReadonlySet<string> = new Set(REVIEW_STATUSES);

/** Keys of `source_metadata` the worker writes (`provenance` in pixano_worker/writer.py). */
const METADATA_MODEL_KEY = "model";
const METADATA_MODEL_VERSION_KEY = "model_version";

/** A score below this is the backend's "not predicted" sentinel (-1), not a score. */
const MIN_CONFIDENCE = 0;

/** Whether a value read from outside — a row, a form control — is a review status. */
export function isReviewStatus(value: unknown): value is ReviewStatus {
  return typeof value === "string" && KNOWN_STATUSES.has(value);
}

/**
 * A model row always has a status. One written without it — re-imported from a
 * format that does not carry it — is still a model's output nobody reviewed,
 * which is what `pending` means (the server reads it the same way:
 * `review_status_of` in src/pixano/schemas/annotations/review.py).
 */
function statusOf(value: unknown, isModel: boolean): ReviewStatus | "" {
  if (isReviewStatus(value)) return value;
  return isModel ? REVIEW_STATUS.PENDING : "";
}

/**
 * `source_metadata` is a JSON object serialized to a string. Anything else —
 * malformed JSON, an array, a number — reads as "no metadata": a row with
 * unreadable provenance must still load and show its status.
 */
function parseSourceMetadata(value: unknown): Record<string, unknown> {
  let parsed: unknown = value;
  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value);
    } catch {
      return {};
    }
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) return {};
  return parsed as Record<string, unknown>;
}

function nonEmptyString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function confidenceOf(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) && value >= MIN_CONFIDENCE
    ? value
    : undefined;
}

/**
 * A score column's value as one score: the value itself, or the first score of
 * a list holding one per label.
 */
function scoreIn(value: unknown): number | undefined {
  if (!Array.isArray(value)) return confidenceOf(value);
  for (const item of value as unknown[]) {
    const score = confidenceOf(item);
    if (score !== undefined) return score;
  }
  return undefined;
}

/**
 * The model's score of a row: the first of the kind's score columns, in the
 * order it declares them, that holds one.
 */
function scoreOf(row: EntityAnnotationColumns, scoreFields: readonly string[]): number | undefined {
  const columns = row as Readonly<Record<string, unknown>>;
  for (const field of scoreFields) {
    const score = scoreIn(columns[field]);
    if (score !== undefined) return score;
  }
  return undefined;
}

/**
 * Read an annotation row's review state. Lenient by design — it never throws:
 * a row a newer or older backend wrote, or one imported with odd provenance,
 * still loads, with whatever could be read.
 *
 * @param row The stored row.
 * @param scoreFields The columns holding the model's score on the row's kind,
 *   as its seed loader declares them; none for a kind with no score. Each kind
 *   names its own, so this module knows no column of any kind.
 */
export function reviewOf(
  row: EntityAnnotationColumns,
  scoreFields: readonly string[] = [],
): AnnotationReview {
  const sourceType = typeof row.source_type === "string" ? row.source_type : "";
  const metadata = parseSourceMetadata(row.source_metadata);
  const status = statusOf(row.review_status, sourceType === MODEL_SOURCE_TYPE);
  return {
    status,
    storedStatus: status,
    sourceType,
    sourceName: typeof row.source_name === "string" ? row.source_name : "",
    model: nonEmptyString(metadata[METADATA_MODEL_KEY]),
    modelVersion: nonEmptyString(metadata[METADATA_MODEL_VERSION_KEY]),
    confidence: scoreOf(row, scoreFields),
    scoreFields,
  };
}

/** The status the dataset holds for the row (see `AnnotationReview.storedStatus`). */
export function storedStatusOf(review: AnnotationReview): ReviewStatus | "" {
  return review.storedStatus ?? review.status;
}

/**
 * Whether the row shows an Accept the dataset does not hold yet: shown
 * accepted, stored otherwise. Such an Accept rides on every update of the row
 * queued until it is saved.
 */
export function isAcceptUnsaved(review: AnnotationReview): boolean {
  return (
    review.status === REVIEW_STATUS.ACCEPTED && storedStatusOf(review) !== REVIEW_STATUS.ACCEPTED
  );
}

/**
 * Whether a reviewer decides on this annotation: it is stored, and a model
 * produced it. A draft or a person's annotation has nothing to review.
 */
export function isReviewable(annotation: LocalAnnotation): annotation is ReviewableAnnotation {
  const review = annotation.review;
  return (
    annotation.persisted &&
    review !== undefined &&
    review.sourceType === MODEL_SOURCE_TYPE &&
    isReviewStatus(review.status)
  );
}

/** The chip an annotation falls under: its status for a model's row, "human" otherwise. */
export function reviewFilterKeyOf(annotation: LocalAnnotation): ReviewFilterKey {
  return isReviewable(annotation) ? annotation.review.status : HUMAN_REVIEW_FILTER;
}

/**
 * Whether the status filter lets this annotation show. A draft always shows:
 * it is being drawn, and hiding it would hide the gesture from the person
 * making it.
 */
export function isShownByReviewFilter(
  annotation: LocalAnnotation,
  hidden: ReadonlySet<ReviewFilterKey>,
): boolean {
  return !annotation.persisted || !hidden.has(reviewFilterKeyOf(annotation));
}

/**
 * Whether a reviewer may accept a model's row now, by what the screen shows:
 * only a row shown pending is offered Accept — the one rule every control that
 * offers it reads.
 *
 * A row shown pending is stored pending: nothing but the worker sets the
 * status, and no update takes a row back from accepted. An unsaved edit does
 * not stand in the way: it leaves the row in review until it is saved or
 * accepted, and an Accept rides on it (`commitAccept`). A row shown accepted —
 * stored so, accepted and not saved yet, or its edit on the wire — has nothing
 * left to accept.
 *
 * @param review The row's review state.
 */
export function mayAccept(review: AnnotationReview): boolean {
  return review.status === REVIEW_STATUS.PENDING;
}

/**
 * The status the dataset holds for a model's row once a write of it with this
 * body has landed — what the server's rules store (`_as_human_edit_of` in
 * src/pixano/api/service.py):
 *
 * - an Accept stores `accepted`;
 * - a change to the row's content stores `accepted` too: a person who saves an
 *   edit of a model's row chooses to keep it. The interface queues no edit
 *   that leaves the content as stored, so a body carrying content is a change;
 * - anything else — an echo, `pending`, which only the worker sets — leaves the
 *   status as it was.
 *
 * A row no model produced has no status to move.
 *
 * @param review The row's review state.
 * @param body The body of the update.
 */
export function storedStatusAfterWrite(
  review: AnnotationReview,
  body: Readonly<Record<string, unknown>>,
): ReviewStatus | "" {
  const stored = storedStatusOf(review);
  if (review.sourceType !== MODEL_SOURCE_TYPE) return stored;
  const accepts = body[REVIEW_STATUS_FIELD] === REVIEW_STATUS.ACCEPTED;
  return accepts || carriesContent(body) ? REVIEW_STATUS.ACCEPTED : stored;
}

/**
 * Whether an update body changes the row's content — its geometry, its entity
 * — rather than carrying an Accept alone, whose body is the status and
 * nothing else.
 */
export function carriesContent(body: Readonly<Record<string, unknown>>): boolean {
  return Object.keys(body).some((key) => key !== REVIEW_STATUS_FIELD);
}
