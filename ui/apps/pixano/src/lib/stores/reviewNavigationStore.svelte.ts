/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { currentDatasetStore, currentItemSaveCoordinator } from "./appStores.svelte";
import { reactiveStore } from "./reactiveStore.svelte";
import { reviewDecisionsLockedOn, reviewModeIsActive } from "./workspaceBaseStores.svelte";
import { navigating, page } from "$app/state";
import { getNextRecordToReview } from "$lib/api/reviewApi";
import { navigateToRoute } from "$lib/utils/navigation";
import { saveAndOpenNext, type SaveAndNextOutcome } from "$lib/utils/reviewNavigation";
import { getReviewRoute } from "$lib/utils/routes";

// "Save & next" as the workspace runs it: one run at a time, and no review decision on the record
// it leaves.

/** Whether "Save & next" is running. */
export const movingToNextRecord = reactiveStore<boolean>(false);

/** The record whose queue of records to review could not be read, if any. */
export const unreadableQueueRecord = reactiveStore<string | null>(null);

/**
 * Save the open record, then open the next record to review.
 *
 * @returns What "Save & next" did, or null when it could not start: one already runs, another
 *   record is being opened, or no record is open.
 */
export async function saveAndOpenNextRecord(): Promise<SaveAndNextOutcome | null> {
  const datasetId = currentDatasetStore.value?.id;
  const recordId = page.params.itemId;
  if (!datasetId || !recordId || movingToNextRecord.value || navigating.to !== null) return null;
  movingToNextRecord.value = true;
  // A decision taken from the save to the next record's opening would land on a record being
  // left. Another change made meanwhile is caught by the unsaved-changes guard.
  reviewDecisionsLockedOn.value = recordId;
  try {
    const outcome = await saveAndOpenNext(recordId, {
      save: async () => (await currentItemSaveCoordinator.requestSave()).ok,
      nextAfter: (after) => getNextRecordToReview(datasetId, after),
      // Still on it, in review, with no other record being opened.
      isStillOpen: (record) =>
        page.params.itemId === record && navigating.to === null && reviewModeIsActive.value,
      open: (record) => navigateToRoute(getReviewRoute(datasetId, record)),
    });
    if (outcome.kind === "queue-unreadable") unreadableQueueRecord.value = recordId;
    return outcome;
  } finally {
    reviewDecisionsLockedOn.value = null;
    movingToNextRecord.value = false;
  }
}
