/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Viewport } from "./layoutPlanner.js";
import type { ReviewGateway } from "./reviewGateway.js";
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
  isReviewStatus,
  isShownByReviewFilter,
  mayAccept,
  REVIEW_FILTER_KEYS,
  REVIEW_STATUS,
  reviewFilterKeyOf,
  type ReviewFilterKey,
  type ReviewStatus,
} from "$lib/annotations/reviewStatus.js";
import type { MutationSink } from "$lib/annotations/scene/sceneContext.js";
import { pickEntityLabel } from "$lib/annotations/types.js";

/**
 * The source id the review panel stamps on the work it queues — its Accepts,
 * and the deletes its Rejects send — in the `widgetId` slot of a mutation. The
 * panel is not a widget; every unsaved counter — the widgets' toolbars and the
 * Review tab — is record-wide, so the decisions show wherever the reviewer
 * looks.
 */
export const REVIEW_PANEL_SOURCE_ID = "review-panel";

/** What a save came to, as it ended. */
export interface SaveReport {
  /** The save went through and left nothing unsaved. */
  readonly saved: boolean;
  /** The save itself failed: the error is on the workspace's `saveError`. */
  readonly failed: boolean;
}

/** How the controller saves and moves between records, without knowing the manager. */
export interface ReviewNavigator {
  /**
   * Save every queued change. Says whether it failed as it ends: a save
   * started meanwhile clears the workspace's error, which is no record of this
   * one's.
   */
  save(): Promise<SaveReport>;
  /**
   * How many items of the open record are unsaved — the workspace's one count,
   * which every widget toolbar shows too (`WorkspaceManager.unsavedCount`).
   */
  unsavedCount(): number;
  /** Whether the open record holds work not saved yet — a change, a draft, a staged edit. */
  hasUnsavedWork(): boolean;
  /** Throw away every unsaved change of the open record. */
  discardChanges(): Promise<void>;
  /**
   * Replace the open record with another one of the same dataset — "Save &
   * next"'s own move, which does not end its hold as any other opening does
   * (`ReviewController.recordOpening`).
   */
  openRecord(datasetId: string, recordId: string, viewport?: Viewport): Promise<void>;
}

/** Everything the controller depends on, each as narrow as it can be. */
export interface ReviewControllerDeps {
  session: WorkspaceSession;
  /** The mutation queue, through the same interface tools see. */
  sink: MutationSink;
  navigator: ReviewNavigator;
  gateway: ReviewGateway;
}

/**
 * Why a model's row is not offered Accept: it reads accepted already, so
 * nothing is left to accept, or "Save & next" holds the decisions back.
 */
export type AcceptRefusal = "accepted" | "busy";

/** Why a model's row is not offered Reject: "Save & next" holds the decisions back. */
export type RejectRefusal = "busy";

/** One line of the review list: what the panel shows, already read from the annotation. */
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
  /** Why Accept is not offered on a model's row; null when it is, and on a person's row. */
  acceptRefusal: AcceptRefusal | null;
  canReject: boolean;
  /** Why Reject is not offered on a model's row; null when it is, and on a person's row. */
  rejectRefusal: RejectRefusal | null;
  selected: boolean;
}

/** What the last "Save & next" came to, for the panel to put into words. */
export type NextRecordOutcome =
  | { kind: "opened"; recordId: string; status: ReviewStatus; remaining: number }
  | { kind: "none-left"; status: ReviewStatus }
  /**
   * The record stays open: the save failed (`saveFailed`), or went through and
   * left work unsaved (no `saveFailed`). Which one is taken as "Save & next"
   * stops, so the words never come from a later save's error.
   */
  | { kind: "not-saved"; saveFailed?: true }
  | { kind: "failed"; message: string };

/** The "not saved" outcome, saying whether the save itself failed. */
function notSaved(saveFailed: boolean): NextRecordOutcome {
  return saveFailed ? { kind: "not-saved", saveFailed: true } : { kind: "not-saved" };
}

/** What a list line reads beyond the annotation itself. */
interface RowContext {
  selectedId: string | null;
  /** The queue, for the lock that offers neither Accept nor Reject while "Save & next" runs. */
  sink: Pick<MutationSink, "decisionsLocked">;
}

/**
 * Why a model's row is not offered Accept, or null when it is — or when the row
 * is a person's, which takes no decision. A row shown accepted has nothing left
 * to accept, even while "Save & next" runs, so the panel never promises an
 * Accept no run will make possible; one shown pending waits for the run.
 */
function acceptRefusalOf(annotation: LocalAnnotation, offered: boolean): AcceptRefusal | null {
  if (offered || !isReviewable(annotation)) return null;
  return mayAccept(annotation.review) ? "busy" : "accepted";
}

function toRow(annotation: LocalAnnotation, ctx: RowContext): ReviewRow {
  const review = annotation.review;
  const reviewable = isReviewable(annotation);
  const acceptOffered = canAccept(annotation, ctx.sink);
  const deleteGesture = deleteGestureFor(annotation, ctx.sink);
  return {
    id: annotation.id,
    kind: annotation.kind,
    label: pickEntityLabel(annotation.entity),
    source: reviewable ? (review?.model ?? review?.sourceName ?? "") : "",
    modelVersion: reviewable ? review?.modelVersion : undefined,
    confidence: reviewable ? review?.confidence : undefined,
    filterKey: reviewFilterKeyOf(annotation),
    persisted: annotation.persisted,
    canAccept: acceptOffered,
    acceptRefusal: acceptRefusalOf(annotation, acceptOffered),
    // A model's stored row, while no "Save & next" holds rejects back.
    canReject: deleteGesture === "reject",
    rejectRefusal: deleteGesture === "locked" ? "busy" : null,
    selected: annotation.id === ctx.selectedId,
  };
}

/**
 * The review of the open record: what the Review tab lists and counts, the
 * status chips that filter it and the canvas, the decisions, and "Save &
 * next" to the next record holding annotations of a chosen status.
 *
 * Holds no review state of its own beyond "Save & next" (the status it looks
 * for, its progress, its outcome): the statuses live on the annotations, the
 * decisions on the mutation queue, the chips on the session — so a widget, a
 * keyboard shortcut and the Review tab all see the same thing. Kind-agnostic: a
 * kind added later is listed, filtered and decided on without a line here.
 */
export class ReviewController {
  /** The status "Save & next" looks for. */
  nextStatus = $state<ReviewStatus>(REVIEW_STATUS.PENDING);
  /**
   * The last "Save & next" outcome, with the record it was reached on. Kept
   * apart from `outcome` so a record opened another way — from the record list
   * — does not go on showing a message about a different one.
   */
  private lastOutcome = $state<{ recordId: string; value: NextRecordOutcome } | null>(null);

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
    const ctx: RowContext = { selectedId: collection.selectedId, sink: this.deps.sink };
    return collection.items
      .filter((a) => isShownByReviewFilter(a, hidden))
      .filter((a) => !a.persisted || session.isEntityVisible(a.entityId))
      .map((a) => toRow(a, ctx));
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

  constructor(private readonly deps: ReviewControllerDeps) {
    // "Not moved" is over once the record has nothing unsaved — the work that
    // kept the reviewer there finished, saved or let go — and is cleared then,
    // not merely hidden: work begun later is no reason "Save & next" gave.
    // Watched for the controller's life, which is the workspace's.
    $effect.root(() => {
      $effect(() => {
        if (this.lastOutcome?.value.kind === "not-saved" && !deps.navigator.hasUnsavedWork()) {
          this.lastOutcome = null;
        }
      });
    });
  }

  /**
   * True while "Save & next" is saving the open record or moving from it — the
   * time it holds the workspace's decision lock
   * (`WorkspaceSession.decisionsLocked`), which every decision path reads.
   */
  get navigating(): boolean {
    return this.deps.session.decisionsLocked;
  }

  /**
   * Unsaved items on the whole record — decisions, edits, drafts, work a tool
   * holds — counted where the widget toolbars' count is, so the two agree.
   */
  get unsavedCount(): number {
    return this.deps.navigator.unsavedCount();
  }

  /**
   * Whether the Review tab's Save has anything to send: a queued change. Work
   * a tool holds, or a draft whose entity is still being chosen, is unsaved
   * too, but is finished in its tool or form before a save can carry it.
   */
  get canSave(): boolean {
    return this.deps.sink.pending.length > 0;
  }

  /**
   * Whether the Review tab's Discard has anything to throw away: a queued
   * change, a draft, or work a tool holds staged with an empty queue.
   */
  get canDiscard(): boolean {
    return this.deps.navigator.hasUnsavedWork();
  }

  /**
   * What the last "Save & next" came to, while the record it left the reviewer
   * on is open. "Not saved" lasts until the reviewer acts on what kept them
   * there: it is cleared by the next save or Discard (`clearNotMoved`), a
   * record opened (`recordOpening`), or the record having nothing unsaved any
   * more (the constructor's watch) — and reads as over from that very moment.
   */
  get outcome(): NextRecordOutcome | null {
    const last = this.lastOutcome;
    if (!last || last.recordId !== this.deps.session.recordId) return null;
    if (last.value.kind === "not-saved" && !this.deps.navigator.hasUnsavedWork()) return null;
    return last.value;
  }

  /**
   * Clear a "not moved" outcome: the record is being saved or discarded, from
   * whichever control, so what "Save & next" stopped on is no longer the
   * question. The workspace calls it on each save and each Discard.
   */
  clearNotMoved(): void {
    if (this.lastOutcome?.value.kind === "not-saved") this.lastOutcome = null;
  }

  /**
   * Told by the workspace as a record is about to open other than by "Save &
   * next"'s own move (`ReviewNavigator.openRecord`) — from the record list,
   * another record or the same one opened again. A "Save & next" still running
   * loses its decision lock: the reviewer has taken the record in hand, the run
   * will move nobody, and decisions are theirs again at once. Its last outcome
   * is forgotten: it was about a record as it was before.
   */
  recordOpening(): void {
    this.deps.session.decisionLock = null;
    this.lastOutcome = null;
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
   * (`commitAccept`). Returns whether it was accepted. Not while "Save & next"
   * runs: the Accept would land on a record the reviewer is being moved away
   * from — the lock `commitAccept` reads, as on every other path.
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
   * Reject a model's annotation from the panel: delete it, as every delete
   * gesture on a model's row does (`deleteLocalAnnotation`). Returns whether the
   * delete was queued — the row is then gone from the record. Refused on what
   * is not a model's stored row, and while "Save & next" runs, under the same
   * lock as an Accept.
   */
  reject(annotationId: string): boolean {
    const collection = this.deps.session.annotations;
    const annotation = collection.find(annotationId);
    if (!annotation || deleteGestureFor(annotation, this.deps.sink) !== "reject") return false;
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

  // ─── Saving and moving on ─────────────────────────────────────────────────

  /** Choose the status "Save & next" looks for; anything else is ignored. */
  setNextStatus(value: string): void {
    if (isReviewStatus(value)) this.nextStatus = value;
  }

  /** Send every unsaved change of the record — the Review tab's Save. */
  async save(): Promise<boolean> {
    return (await this.deps.navigator.save()).saved;
  }

  /** Throw away every unsaved change of the record — the Review tab's Discard. */
  discard(): Promise<void> {
    return this.deps.navigator.discardChanges();
  }

  /**
   * Save, then open the next record holding annotations of `nextStatus`.
   *
   * Saving comes first because opening a record clears the queue: moving on
   * must never lose a decision. A failed save — or one that leaves work
   * unsaved, such as a draft still waiting for its entity — stays on the
   * record, with the work as the person left it. When no *other* record holds
   * that status — the server wraps round, so the answer can be the open record
   * itself — nothing is reopened.
   *
   * The reviewer can still act while it runs, though not decide: draw, edit,
   * open a record from the list. So it looks again after each step: it stays
   * on a record that holds unsaved work once the next one is known, and moves
   * nobody away from a record they opened themselves meanwhile — nor from the
   * same record opened again: opening one ends the run's hold.
   */
  async saveAndNext(viewport?: Viewport): Promise<void> {
    const session = this.deps.session;
    const { datasetId, recordId } = session;
    if (!datasetId || !recordId || this.navigating) return;
    const status = this.nextStatus;
    // The run's hold on the workspace: no decision is taken on any path — the
    // Review tab, the Delete key, a trash button, a HUD — since it would land on
    // a record the reviewer is being moved from. Let go as the run ends,
    // whatever it comes to; taken away from it when the reviewer opens a record,
    // this one included (`recordOpening`), after which the run moves nobody and
    // says nothing.
    let lock = { datasetId, recordId };
    session.decisionLock = lock;
    const stillHeld = () => session.decisionLock === lock;
    this.lastOutcome = null;
    try {
      const report = await this.deps.navigator.save();
      if (!stillHeld()) return;
      if (!report.saved) {
        this.lastOutcome = { recordId, value: notSaved(report.failed) };
        return;
      }
      const next = await this.deps.gateway.nextRecordToReview(datasetId, {
        status,
        after: recordId,
      });
      if (!stillHeld()) return;
      if (this.deps.navigator.hasUnsavedWork()) {
        this.lastOutcome = { recordId, value: notSaved(false) };
        return;
      }
      if (next.recordId === null || next.recordId === recordId) {
        this.lastOutcome = { recordId, value: { kind: "none-left", status } };
        return;
      }
      // The hold moves with the reviewer onto the record it opens, until it is shown.
      lock = { datasetId, recordId: next.recordId };
      session.decisionLock = lock;
      await this.deps.navigator.openRecord(datasetId, next.recordId, viewport);
      if (!stillHeld()) return;
      this.lastOutcome = {
        recordId: next.recordId,
        value: { kind: "opened", recordId: next.recordId, status, remaining: next.remaining },
      };
    } catch (err) {
      // A run the reviewer left has nothing to say about where they are now.
      if (!stillHeld()) return;
      const message = err instanceof Error ? err.message : String(err);
      // Shown on whichever record is open now: a load that failed half way has
      // already switched the session to the record it was opening.
      const onRecord = session.recordId ?? recordId;
      this.lastOutcome = { recordId: onRecord, value: { kind: "failed", message } };
    } finally {
      if (session.decisionLock === lock) session.decisionLock = null;
    }
  }
}
