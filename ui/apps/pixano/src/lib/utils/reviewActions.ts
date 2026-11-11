/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  ENTITY_RESOURCE,
  resourceForSchema,
  toAcceptMutation,
  type ResourceMutation,
} from "$lib/api/resourcePayloads";
import { getResource, type StoredRow } from "$lib/api/schemaApi";
import { REVIEW_STATUS, REVIEW_STATUS_FIELD } from "$lib/constants/reviewConstants";
import {
  annotations,
  entities,
  highlightedEntity,
  preAnnotationIsActive,
  selectedTool,
  workspaceSaveQueue,
} from "$lib/stores/workspaceStores.svelte";
import { ToolType } from "$lib/tools";
import type { Annotation, Entity } from "$lib/types/dataset";
import { deleteEntity } from "$lib/utils/entityDeletion";
import { clearFocusedEntity } from "$lib/utils/highlightOperations";
import { isPendingReview, pendingReviewOf } from "$lib/utils/reviewStatus";
import { saveTo } from "$lib/utils/saveItemUtils";

// The review decisions on a model's annotations, and what a save stored of them.
//
// A decision is staged like any edit and saved with the record's other changes: leaving the
// record without saving drops it. An Accept is shown at once (`unsavedAccept`) and sends the
// status alone, or rides on the row's write when the row is edited too; a Reject deletes the row.
// Every control that decides goes through here, so that one rule says when a decision may be
// taken.

/**
 * Whether a review decision may be taken now: not under the Fusion tool, which merges objects;
 * not while the old pre-annotation mode hides the list of objects.
 */
export function canTakeReviewDecision(): boolean {
  return selectedTool.value?.type !== ToolType.Fusion && !preAnnotationIsActive.value;
}

/**
 * The annotations an object's own Accept or Reject decides on: those still to review that it
 * shows. One hidden, by its eye or by a filter, stays to review.
 */
export function reviewTargetsOf(object: Entity): Annotation[] {
  return pendingReviewOf(object.ui.childs ?? []).filter(
    (annotation) => !annotation.ui.displayControl.hidden,
  );
}

/**
 * Stage the Accept of a row. Alone, it sends the status alone, so that the row is stored as the
 * model wrote it. A write of the row staged or being sent is an edit: the Accept rides on it, the
 * row sent whole, since a later write of a row replaces the one staged before it.
 */
function stageAccept(annotation: Annotation): void {
  const isWritten = workspaceSaveQueue.mutations.some(
    (mutation) => mutation.target.id === annotation.id,
  );
  if (isWritten) saveTo("update", annotation);
  else workspaceSaveQueue.stage(toAcceptMutation(annotation));
}

/**
 * Accept these annotations, each still to review: shown accepted, and the Accept staged. Those
 * already accepted, or not reviewed here, are left as they are.
 */
export function acceptAnnotations(toAccept: readonly Annotation[]): void {
  if (!canTakeReviewDecision()) return;
  const ids = new Set(toAccept.filter(isPendingReview).map((annotation) => annotation.id));
  if (ids.size === 0) return;
  annotations.update((current) =>
    current.map((annotation) => {
      if (ids.has(annotation.id)) annotation.ui.unsavedAccept = true;
      return annotation;
    }),
  );
  for (const annotation of annotations.value) {
    if (ids.has(annotation.id)) stageAccept(annotation);
  }
}

/**
 * Reject these annotations, each still to review: each is deleted, with its object once it was
 * the object's last annotation, as the inspector's delete does. Those already accepted, or not
 * reviewed here, are left as they are.
 */
export function rejectAnnotations(toReject: readonly Annotation[]): void {
  if (!canTakeReviewDecision()) return;
  for (const annotation of toReject.filter(isPendingReview)) {
    // Looked up for each: a delete rebuilds the object's list of annotations.
    const entity = entities.value.find((candidate) => candidate.id === annotation.data.entity_id);
    if (entity) deleteEntity(entity, annotation);
  }
  // A focus left on an object deleted would fade every annotation (`getEffectiveHighlight`).
  const focusedId = highlightedEntity.value;
  if (focusedId !== null && !entities.value.some((entity) => entity.id === focusedId)) {
    clearFocusedEntity();
  }
}

/** Show these annotations as the dataset now holds them: accepted. */
function showStoredAccepted(ids: ReadonlySet<string>): void {
  if (ids.size === 0) return;
  annotations.update((current) =>
    current.map((annotation) => {
      if (ids.has(annotation.id)) {
        annotation.data = { ...annotation.data, [REVIEW_STATUS_FIELD]: REVIEW_STATUS.ACCEPTED };
        annotation.ui.unsavedAccept = false;
      }
      return annotation;
    }),
  );
}

/**
 * The rows naming these entities that the server accepted with their edits, read back, all at
 * once. A row that cannot be read back stays as it was shown: the next opening of the record
 * reads its stored status.
 */
async function acceptedWithEntities(
  entityIds: ReadonlySet<string>,
  datasetId: string,
): Promise<Set<string>> {
  const toReadBack = annotations.value.filter(
    (annotation) => entityIds.has(annotation.data.entity_id) && isPendingReview(annotation),
  );
  const accepted = new Set<string>();
  await Promise.all(
    toReadBack.map(async (annotation) => {
      try {
        const row = await getResource(
          datasetId,
          resourceForSchema(annotation),
          annotation.table_info.name,
          annotation.id,
        );
        if (row[REVIEW_STATUS_FIELD] === REVIEW_STATUS.ACCEPTED) accepted.add(annotation.id);
      } catch {
        // Left as shown; the record's next opening reads the stored status.
      }
    }),
  );
  return accepted;
}

/** What a save stores of the review, gathered while it runs and shown once it ends. */
export interface ReviewReflection {
  /** Told of each write the server stored (`persistSaveItems`). */
  onPersisted: (mutation: ResourceMutation, stored: StoredRow | undefined) => void;
  /** Reads back what the save's edits of entities accepted. Never throws. */
  finish: () => Promise<void>;
}

/**
 * Follow a save, to show what it stored of the review.
 *
 * - A write of a model's row: the status of the row the server answered with. Saving an Accept or
 *   an edit of a model's row accepts it; a write that carried the Accept is enough when the
 *   answer holds no row.
 * - An update of an entity: a person's edit of what an entity says accepts the model's rows
 *   naming it (`acceptances_of_entity_edit` in src/pixano/api/review.py). Whether it did depends
 *   on the entity the server held before, which this app does not keep: once the save ends, the
 *   rows naming an edited entity and still shown pending are read back.
 *
 * A row only ever moves to accepted: no update takes it back.
 *
 * @param datasetId The dataset of the open record.
 */
export function createReviewReflection(datasetId: string): ReviewReflection {
  const editedEntities = new Set<string>();
  return {
    onPersisted(mutation, stored) {
      if (mutation.op === "delete") return;
      if (mutation.target.resource === ENTITY_RESOURCE) {
        if (mutation.op === "update") editedEntities.add(mutation.target.id);
        return;
      }
      const storesAccepted = stored?.[REVIEW_STATUS_FIELD] === REVIEW_STATUS.ACCEPTED;
      const carriedAccept = mutation.body?.[REVIEW_STATUS_FIELD] === REVIEW_STATUS.ACCEPTED;
      if (storesAccepted || (stored === undefined && carriedAccept)) {
        showStoredAccepted(new Set([mutation.target.id]));
      }
    },
    async finish() {
      if (editedEntities.size === 0) return;
      showStoredAccepted(await acceptedWithEntities(editedEntities, datasetId));
    },
  };
}
