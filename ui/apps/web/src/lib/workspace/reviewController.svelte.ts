/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { WorkspaceSession } from "./workspaceSession.svelte.js";
import type {
  AnnotationKind,
  LocalAnnotation,
} from "$lib/annotations/annotationCollection.svelte.js";
import {
  canAccept,
  commitAccept,
  deleteGestureFor,
  deleteLocalAnnotation,
} from "$lib/annotations/payloadBuilders.js";
import {
  isReviewable,
  isShownByReviewFilter,
  REVIEW_FILTER_KEYS,
  reviewFilterKeyOf,
  type ReviewFilterKey,
} from "$lib/annotations/reviewStatus.js";
import type { MutationSink } from "$lib/annotations/scene/sceneContext.js";
import { pickEntityLabel } from "$lib/annotations/types.js";

/**
 * The source id the review controller stamps on the work it queues — its
 * Accepts, and the deletes its Rejects send — in the `widgetId` slot of a
 * mutation. The review panel is not a widget; every unsaved counter is
 * record-wide, so the decisions show wherever the reviewer looks.
 */
export const REVIEW_PANEL_SOURCE_ID = "review-panel";

/** How the controller saves and discards the open record, without knowing the manager. */
export interface ReviewNavigator {
  /** Save every queued change. Resolves true when it went through and left nothing unsaved. */
  save(): Promise<boolean>;
  /**
   * How many items of the open record are unsaved — the workspace's one count,
   * which every widget toolbar shows too (`WorkspaceManager.unsavedCount`).
   */
  unsavedCount(): number;
  /** Whether the open record holds work not saved yet — a change, a draft, a staged edit. */
  hasUnsavedWork(): boolean;
  /** Throw away every unsaved change of the open record. */
  discardChanges(): Promise<void>;
}

/** Everything the controller depends on, each as narrow as it can be. */
export interface ReviewControllerDeps {
  session: WorkspaceSession;
  /** The mutation queue, through the same interface tools see. */
  sink: MutationSink;
  navigator: ReviewNavigator;
}

/** One line of the review list: what a panel shows, already read from the annotation. */
export interface ReviewRow {
  id: string;
  kind: AnnotationKind;
  /** The entity's label, as the canvas writes it. */
  label: string;
  /** The model that produced the row — or, when not recorded, its source's name. Empty for a person's row. */
  source: string;
  modelVersion?: string;
  confidence?: number;
  /** The row's status, or "human" for a row no model produced. */
  filterKey: ReviewFilterKey;
  /** False for a draft, which has no row in the dataset yet. */
  persisted: boolean;
  canAccept: boolean;
  canReject: boolean;
  selected: boolean;
}

function toRow(annotation: LocalAnnotation, selectedId: string | null): ReviewRow {
  const review = annotation.review;
  const reviewable = isReviewable(annotation);
  return {
    id: annotation.id,
    kind: annotation.kind,
    label: pickEntityLabel(annotation.entity),
    source: reviewable ? (review?.model ?? review?.sourceName ?? "") : "",
    modelVersion: reviewable ? review?.modelVersion : undefined,
    confidence: reviewable ? review?.confidence : undefined,
    filterKey: reviewFilterKeyOf(annotation),
    persisted: annotation.persisted,
    canAccept: canAccept(annotation),
    // A model's stored row, whatever its status: its Reject deletes it.
    canReject: deleteGestureFor(annotation) === "reject",
    selected: annotation.id === selectedId,
  };
}

/**
 * The review of the open record: what a review panel lists and counts, the
 * status chips that filter it and the canvas, and the decisions.
 *
 * Holds no review state of its own: the statuses live on the annotations, the
 * decisions on the mutation queue, the chips on the session — so a widget, a
 * keyboard shortcut and a panel all see the same thing. Kind-agnostic: a kind
 * added later is listed, filtered and decided on without a line here.
 */
export class ReviewController {
  /**
   * The record's annotations the canvases show, as list lines: those the chips
   * let through, of the entities the Entities tab shows. A line for an
   * annotation no canvas draws would let the reviewer select it, and the
   * Delete key then act on something out of sight.
   */
  readonly rows: ReviewRow[] = $derived.by(() => {
    const session = this.deps.session;
    const collection = session.annotations;
    const hidden = session.hiddenReviewStatuses;
    const selectedId = collection.selectedId;
    return collection.items
      .filter((a) => isShownByReviewFilter(a, hidden))
      .filter((a) => !a.persisted || session.isEntityVisible(a.entityId))
      .map((a) => toRow(a, selectedId));
  });

  /** How many of the record's annotations fall under each chip, hidden or not. */
  readonly counts: Readonly<Record<ReviewFilterKey, number>> = $derived.by(() => {
    const counts = Object.fromEntries(REVIEW_FILTER_KEYS.map((key) => [key, 0])) as Record<
      ReviewFilterKey,
      number
    >;
    for (const annotation of this.deps.session.annotations.items) {
      counts[reviewFilterKeyOf(annotation)]++;
    }
    return counts;
  });

  constructor(private readonly deps: ReviewControllerDeps) {}

  /**
   * Unsaved items on the whole record — decisions, edits, drafts, work a tool
   * holds — counted where the widget toolbars' count is, so the two agree.
   */
  get unsavedCount(): number {
    return this.deps.navigator.unsavedCount();
  }

  /**
   * Whether Save has anything to send: a queued change. Work a tool holds, or
   * a draft whose entity is still being chosen, is unsaved too, but is
   * finished in its tool or form before a save can carry it.
   */
  get canSave(): boolean {
    return this.deps.sink.pending.length > 0;
  }

  /**
   * Whether Discard has anything to throw away: a queued change, a draft, or
   * work a tool holds staged with an empty queue.
   */
  get canDiscard(): boolean {
    return this.deps.navigator.hasUnsavedWork();
  }

  // ─── Status chips ─────────────────────────────────────────────────────────

  isHidden(key: ReviewFilterKey): boolean {
    return this.deps.session.hiddenReviewStatuses.has(key);
  }

  /** Show or hide one chip's annotations, in the list and on every canvas. */
  toggle(key: ReviewFilterKey): void {
    const hidden = new Set(this.deps.session.hiddenReviewStatuses);
    if (hidden.has(key)) hidden.delete(key);
    else hidden.add(key);
    // Assigned, not mutated in place: a Set's add/delete is not tracked.
    this.deps.session.hiddenReviewStatuses = hidden;
    this.dropSelectionIfHidden();
  }

  /** Whether the chips let this annotation show (drafts always do). */
  isShown(annotation: LocalAnnotation): boolean {
    return isShownByReviewFilter(annotation, this.deps.session.hiddenReviewStatuses);
  }

  // ─── Selection and decisions ──────────────────────────────────────────────

  /** Select a listed annotation; the widgets showing it follow. */
  select(annotationId: string): void {
    this.deps.session.annotations.select(annotationId);
  }

  /**
   * Accept a model's annotation, through the same helper as any other control
   * (`commitAccept`). Returns whether it was accepted.
   */
  accept(annotationId: string): boolean {
    const collection = this.deps.session.annotations;
    const annotation = collection.find(annotationId);
    if (!annotation) return false;
    const accepted = commitAccept(annotation, {
      collection,
      mutations: this.deps.sink,
      widgetId: REVIEW_PANEL_SOURCE_ID,
    });
    if (accepted) this.dropSelectionIfHidden();
    return accepted;
  }

  /**
   * Reject a model's annotation: delete it, as every delete gesture on a
   * model's row does (`deleteLocalAnnotation`). Returns whether the delete was
   * queued — the row is then gone from the record. Refused on what is not a
   * model's stored row.
   */
  reject(annotationId: string): boolean {
    const collection = this.deps.session.annotations;
    const annotation = collection.find(annotationId);
    if (!annotation || deleteGestureFor(annotation) !== "reject") return false;
    deleteLocalAnnotation(annotation, collection, this.deps.sink, REVIEW_PANEL_SOURCE_ID);
    return true;
  }

  /**
   * A selection on something no widget displays would leave the delete key
   * acting on an annotation the person cannot see.
   */
  private dropSelectionIfHidden(): void {
    const selected = this.deps.session.annotations.selected;
    if (selected && !this.isShown(selected)) this.deps.session.annotations.select(null);
  }

  // ─── Saving ───────────────────────────────────────────────────────────────

  /** Send every unsaved change of the record. */
  save(): Promise<boolean> {
    return this.deps.navigator.save();
  }

  /** Throw away every unsaved change of the record. */
  discard(): Promise<void> {
    return this.deps.navigator.discardChanges();
  }
}
