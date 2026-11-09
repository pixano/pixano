/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  highlightedEntity,
  mediaViews,
  reviewedAnnotation,
  reviewModeIsActive,
  selectedTool,
} from "$lib/stores/workspaceStores.svelte";
import { ToolType } from "$lib/tools";
import type { Annotation, Entity } from "$lib/types/dataset";
import { ShapeType, type Shape } from "$lib/types/shapeTypes";
import { sortChilds } from "$lib/utils/entityLookupUtils";
import { clearFocusedEntity, highlightEntity } from "$lib/utils/highlightOperations";
import { acceptAnnotations, rejectAnnotations } from "$lib/utils/reviewActions";
import { isPendingReview, shownPendingReviewOf } from "$lib/utils/reviewStatus";

// The review's keys, in review mode. One annotation at a time is under review, shown alone on the
// canvas (`isHiddenByReview`): Enter accepts it, Delete rejects it, and the next one comes under
// review — the next of the same entity, then the first of the next entity. A key never decides on
// an annotation that is not under review: with none, it brings one under review and decides
// nothing. Like Accept all, the keys leave whole an entity one of whose annotations to review is
// hidden (`shownPendingReviewOf`). Once nothing is left, Enter asks to save and go to the next
// record, and a second Enter does.

export type ReviewKeyDecision = "accept" | "reject";

const ACCEPT_KEYS: ReadonlySet<string> = new Set(["Enter"]);
// A Mac keyboard's delete key sends Backspace: both reject, as both delete in the workspace.
const REJECT_KEYS: ReadonlySet<string> = new Set(["Delete", "Backspace"]);

/** What the review reads of a key event. */
export interface ReviewKeyEvent {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
  repeat: boolean;
  defaultPrevented: boolean;
}

/**
 * The decision a key asks for, or null: another key, a key with a modifier, a key held down —
 * one press, one decision — or one another handler took.
 */
export function reviewDecisionOfKey(event: ReviewKeyEvent): ReviewKeyDecision | null {
  if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return null;
  if (event.repeat || event.defaultPrevented) return null;
  if (ACCEPT_KEYS.has(event.key)) return "accept";
  if (REJECT_KEYS.has(event.key)) return "reject";
  return null;
}

/** How a key answers the prompt to save and go to the next record. */
export type PromptAnswer = "go" | "stay" | "none";

const MODIFIER_KEYS: ReadonlySet<string> = new Set(["Shift", "Control", "Alt", "Meta"]);

/**
 * A key's answer to the prompt to save and go to the next record: Enter goes, any other key stays.
 * A key held down, as the Enter that opened the prompt, and a modifier pressed alone answer
 * nothing.
 */
export function promptAnswerOfKey(event: ReviewKeyEvent): PromptAnswer {
  if (event.repeat || MODIFIER_KEYS.has(event.key)) return "none";
  return reviewDecisionOfKey(event) === "accept" ? "go" : "stay";
}

/** What the workspace is doing when a key comes, as far as the review's keys care. */
export interface ReviewKeyContext {
  /** The selected tool: the keys work with the Pan tool. */
  toolType: ToolType;
  /** What a tool holds of a shape. */
  shape: Shape;
  /** Whether a track or an annotation is in edit mode, which Enter finishes. */
  isEditing: boolean;
  /** Whether a text field has the focus. */
  isTyping: boolean;
  /** Whether the key comes from a dialog, a menu or a list, which handle their own keys. */
  inOverlay: boolean;
  /** Whether a control has the keyboard's focus, which Enter presses. */
  controlHasKeyboardFocus: boolean;
}

/**
 * Whether a tool holds work on a shape: one being drawn, edited or saved. A click on a shape
 * only selects it, which the canvas notes as an edit of no type: no work.
 */
export function shapeHoldsWork(shape: Shape): boolean {
  if (shape.status === "creating" || shape.status === "saving") return true;
  return shape.status === "editing" && shape.type !== ShapeType.none;
}

/** Whether a key is free to take a review decision now, or belongs to something else. */
export function reviewKeyIsFree(decision: ReviewKeyDecision, context: ReviewKeyContext): boolean {
  if (context.toolType !== ToolType.Pan) return false;
  if (context.isTyping || context.inOverlay) return false;
  if (context.isEditing || shapeHoldsWork(context.shape)) return false;
  // Enter presses the control a keyboard user reached; Delete has nothing to press.
  return !(decision === "accept" && context.controlHasKeyboardFocus);
}

/** Whether the Pan tool is selected, the only one the review acts under. */
function panToolIsSelected(): boolean {
  return (selectedTool.value?.type ?? ToolType.Pan) === ToolType.Pan;
}

/** Whether a click on a box puts it in edit mode: not in review, where it selects what to review. */
export function clickEditsBoxes(): boolean {
  return !reviewModeIsActive.value;
}

/**
 * Whether a click beside the shapes keeps the focus: in review, while an annotation is under
 * review — a mask is no target for clicks, and a click on one would end the review of it.
 */
export function clickBesideShapesKeepsFocus(): boolean {
  return reviewModeIsActive.value && reviewedAnnotation.value !== null;
}

/** An annotation the keys go through, with the entity listed for it. */
export interface ReviewTarget {
  object: Entity;
  annotation: Annotation;
}

/**
 * The annotations the keys go through, in order: entity by entity in the order given, the
 * inspector's, and each entity's in the order its card lists them (`sortChilds`).
 */
export function targetsToReview(objects: readonly Entity[]): ReviewTarget[] {
  const viewNames = Object.keys(mediaViews.value);
  return objects.flatMap((object) =>
    [...shownPendingReviewOf(object.ui.childs ?? [])]
      .sort((left, right) => sortChilds(left, right, viewNames))
      .map((annotation) => ({ object, annotation })),
  );
}

/** Bring an annotation under review: shown alone, its entity focused and its card open. */
function bringUnderReview(target: ReviewTarget): void {
  reviewedAnnotation.value = target.annotation.id;
  if (highlightedEntity.value !== target.object.id) highlightEntity(target.object.id, false);
}

/** Put no annotation under review: the canvas shows the record again. */
export function clearAnnotationUnderReview(): void {
  reviewedAnnotation.value = null;
}

/** None is left to review: the whole record shows again, no entity standing out. */
function endReviewOfRecord(): void {
  clearAnnotationUnderReview();
  clearFocusedEntity();
}

/**
 * Bring the first annotation to review under review, as a record opened in review does, so that
 * the keys act on a visible target from the first press. One under review already, as the
 * focused entity's when the review is turned on, is kept.
 *
 * @returns Whether one is under review: false when none is left to review.
 */
export function reviewFirstAnnotation(objects: readonly Entity[]): boolean {
  const targets = targetsToReview(objects);
  if (targets.some((target) => target.annotation.id === reviewedAnnotation.value)) return true;
  const first = targets[0];
  if (first) bringUnderReview(first);
  return first !== undefined;
}

/**
 * Keep the annotation under review with the focused entity. A person who focuses another entity
 * reviews it: from the annotation a click selected (`selectForReview`) or the one in edit mode, if
 * any, else its first. A focus on an entity with nothing to review, or on none, puts none under
 * review.
 */
export function followFocus(objects: readonly Entity[], focusedId: string | null): void {
  const ofFocused = targetsToReview(objects).filter((target) => target.object.id === focusedId);
  if (ofFocused.some((target) => target.annotation.id === reviewedAnnotation.value)) return;
  const edited = ofFocused.find((target) => target.annotation.ui.displayControl.editing);
  reviewedAnnotation.value = (edited ?? ofFocused[0])?.annotation.id ?? null;
}

/**
 * A shape the canvas selected with the Pan tool, in review: it comes under review when it is still
 * to review. Its entity's focus follows (`followFocus` keeps it there). Under another tool, as
 * Fusion, a click picks something else.
 */
export function selectForReview(annotation: Annotation): void {
  if (reviewModeIsActive.value && panToolIsSelected() && isPendingReview(annotation)) {
    reviewedAnnotation.value = annotation.id;
  }
}

/**
 * Keep the annotation under review among those left to review as the annotations change. One
 * decided with the mouse, deleted, hidden — by its eye or a filter — or found gone by a save
 * leaves the review as after a key: the next one comes under review, else none, the record shown
 * whole. Under another tool than Pan, which focuses no entity, it is cleared instead. One that
 * never was to review gives way to the focused entity's.
 *
 * @param before The annotations left to review when it last ran, in order.
 * @param objects The objects the inspector lists, in its order.
 * @returns The annotations left to review now, for its next run.
 */
export function keepUnderReview(
  before: readonly ReviewTarget[],
  objects: readonly Entity[],
): ReviewTarget[] {
  const targets = targetsToReview(objects);
  const current = reviewedAnnotation.value;
  if (current === null || targets.some((target) => target.annotation.id === current)) {
    return targets;
  }
  const index = before.findIndex((target) => target.annotation.id === current);
  if (index < 0) {
    followFocus(objects, highlightedEntity.value);
    return targets;
  }
  if (!panToolIsSelected()) {
    clearAnnotationUnderReview();
    return targets;
  }
  const leftIds = new Set(targets.map((target) => target.annotation.id));
  const nextId = [...before.slice(index + 1), ...before.slice(0, index)].find((target) =>
    leftIds.has(target.annotation.id),
  )?.annotation.id;
  const next = targets.find((target) => target.annotation.id === nextId);
  if (next) bringUnderReview(next);
  else endReviewOfRecord();
  return targets;
}

/**
 * Keep the annotation under review in step with the record: with what is left to review
 * (`keepUnderReview`), then with the focus (`followFocus`). In that order: a Reject that deletes
 * an entity drops the focus on it, and the review moves on before that lost focus could end it.
 *
 * @param before The annotations left to review when it last ran, in order.
 * @param objects The objects the inspector lists, in its order.
 * @returns The annotations left to review now, for its next run.
 */
export function followReview(
  before: readonly ReviewTarget[],
  objects: readonly Entity[],
): ReviewTarget[] {
  const targets = keepUnderReview(before, objects);
  followFocus(objects, highlightedEntity.value);
  return targets;
}

/** What a key did: decided on the annotation under review, brought one under review, or nothing. */
export type ReviewKeyOutcome = "decided" | "brought" | "nothing";

/**
 * Take a key's decision on the annotation under review, then bring the next one under review, or
 * none once it was the last. With none under review, bring one under review instead — the focused
 * entity's, else the first after it — and decide nothing.
 *
 * @param decision The key's decision.
 * @param objects The objects the inspector lists, in its order.
 * @param focusedId The focused entity, if any.
 */
export function takeReviewKey(
  decision: ReviewKeyDecision,
  objects: readonly Entity[],
  focusedId: string | null,
): ReviewKeyOutcome {
  const targets = targetsToReview(objects);
  const index = targets.findIndex((target) => target.annotation.id === reviewedAnnotation.value);
  if (index >= 0) {
    const { annotation } = targets[index];
    const next = [...targets.slice(index + 1), ...targets.slice(0, index)][0];
    if (decision === "accept") acceptAnnotations([annotation]);
    else rejectAnnotations([annotation]);
    if (next) bringUnderReview(next);
    else endReviewOfRecord();
    return "decided";
  }
  const focusedIndex = objects.findIndex((object) => object.id === focusedId);
  const fromFocused = [
    ...objects.slice(Math.max(focusedIndex, 0)),
    ...objects.slice(0, Math.max(focusedIndex, 0)),
  ];
  const target = targetsToReview(fromFocused)[0];
  if (!target) return "nothing";
  bringUnderReview(target);
  return "brought";
}
