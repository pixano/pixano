/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ToolType } from "$lib/tools";
import type { Annotation, Entity } from "$lib/types/dataset";
import { isPendingReview } from "$lib/utils/reviewStatus";

export type HighlightState = "all" | "self" | "none";

/**
 * Walk up the parent chain to find the root (top-level) entity id.
 */
export function getTopEntityId(annotation: Annotation, entitiesById: Map<string, Entity>): string {
  const topEntityId = annotation.ui.top_entities?.[0]?.id;
  if (topEntityId) return topEntityId;

  let entityId = annotation.data.entity_id;
  let entity = entitiesById.get(entityId);
  while (entity && entity.data.parent_id !== "") {
    entityId = entity.data.parent_id;
    entity = entitiesById.get(entityId);
  }
  return entityId;
}

/**
 * Compute effective highlight state for an annotation, taking into account
 * the currently focused entity, the active tool and the review mode.
 *
 * @param reviewing Whether the review mode is on. The stores of a video's frames, which are not
 *   reviewed (`isReviewedHere`), leave it out.
 */
export function getEffectiveHighlight(
  annotation: Annotation,
  focusedEntityId: string | null,
  selectedToolType: ToolType,
  entitiesById: Map<string, Entity> | null,
  reviewing = false,
): HighlightState {
  const focusApplies =
    selectedToolType === ToolType.Pan && Boolean(focusedEntityId) && entitiesById !== null;
  const isFocused =
    focusApplies &&
    entitiesById !== null &&
    getTopEntityId(annotation, entitiesById) === focusedEntityId;
  const ownHighlight = annotation.ui.displayControl.highlighted;
  // In review, what exists already fades and what is still to review stays in plain view, where
  // no tool set a highlight of its own, as Fusion does; a shape being edited stays in view too.
  // Only a focused object stands out: "self" also tells the canvas a shape is selected already,
  // and a click on it would select nothing.
  if (reviewing && ownHighlight === "all") {
    if (isFocused) return "self";
    const isToReview = isPendingReview(annotation) || annotation.ui.displayControl.editing;
    return isToReview ? "all" : "none";
  }
  if (focusApplies) {
    // In Pan mode, a focused entity should visually stand out in context:
    // selected entity = self, every other entity = neutral (none).
    return isFocused ? "self" : "none";
  }
  return ownHighlight;
}

/**
 * The annotation the canvas shows alone, if any: the one under review, in review and with the Pan
 * tool — a drawing tool shows the record whole —, while it names an annotation shown. Deleted or
 * hidden, it hides nothing until the next one comes under review.
 *
 * @param underReviewId The annotation under review, if any.
 */
export function annotationShownAlone(
  annotations: readonly Annotation[],
  underReviewId: string | null,
  reviewing: boolean,
  selectedToolType: ToolType,
): string | null {
  if (!reviewing || selectedToolType !== ToolType.Pan || underReviewId === null) return null;
  const underReview = annotations.find((annotation) => annotation.id === underReviewId);
  return underReview && !underReview.ui.displayControl.hidden ? underReviewId : null;
}

/**
 * Whether the review hides an annotation from the canvas: one annotation is under review, the one
 * the review's keys act on, and it is shown alone, with a shape being edited.
 *
 * @param underReviewId The annotation shown alone, if any (`annotationShownAlone`).
 */
export function isHiddenByReview(annotation: Annotation, underReviewId: string | null): boolean {
  return (
    underReviewId !== null &&
    annotation.id !== underReviewId &&
    !annotation.ui.displayControl.editing
  );
}
