/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { NextRecordToReview } from "$lib/api/restTypes";

// "Save & next": the way from one record to review to the next.
//
// The record is saved first, with its decisions, so that the next record to review is asked of
// the dataset as the save left it: a record whose last annotation to review was just decided
// leaves the queue. The next record follows record id order over the whole dataset, whatever the
// explorer showed.

/** What "Save & next" needs from the workspace, the review queue and the router. */
export interface ReviewNavigationPorts {
  /** Saves the open record; whether everything is saved. */
  save: () => Promise<boolean>;
  /** The next record to review after this one. */
  nextAfter: (recordId: string) => Promise<NextRecordToReview>;
  /** Whether this record is still the one open: the reviewer may have opened another meanwhile. */
  isStillOpen: (recordId: string) => boolean;
  /** Opens a record in review. */
  open: (recordId: string) => Promise<void>;
}

/** What "Save & next" did. */
export type SaveAndNextOutcome =
  /** The save failed: the record stays open, with the save's error and its changes. */
  | { kind: "not-saved" }
  /** The queue could not be read: the record, saved, stays open. */
  | { kind: "queue-unreadable" }
  /** The reviewer opened another record meanwhile, which stays open. */
  | { kind: "left" }
  /** The next record to review is open. */
  | { kind: "opened"; recordId: string; remaining: number }
  /** The open record is the only one left to review: what is left on it may be hidden. */
  | { kind: "last" }
  /** Nothing is left to review in the dataset. */
  | { kind: "done" };

/**
 * Save the open record, then open the next record to review.
 *
 * @param recordId The open record.
 * @param ports The workspace's save, the review queue and the router.
 */
export async function saveAndOpenNext(
  recordId: string,
  ports: ReviewNavigationPorts,
): Promise<SaveAndNextOutcome> {
  if (!(await ports.save())) return { kind: "not-saved" };
  let next: NextRecordToReview;
  try {
    next = await ports.nextAfter(recordId);
  } catch {
    return { kind: "queue-unreadable" };
  }
  if (!ports.isStillOpen(recordId)) return { kind: "left" };
  if (next.record_id === null) return { kind: "done" };
  if (next.record_id === recordId) return { kind: "last" };
  await ports.open(next.record_id);
  return { kind: "opened", recordId: next.record_id, remaining: next.remaining };
}

/**
 * What the workspace says of the records left to review, as the queue last answered for the open
 * record.
 *
 * @param queue The queue's answer for the open record, or null before it came.
 * @param recordId The open record.
 */
export function recordsLeftText(queue: NextRecordToReview | null, recordId: string): string {
  if (queue === null) return "";
  if (queue.remaining === 0) return "All records reviewed";
  if (queue.remaining === 1 && queue.record_id === recordId) {
    return "Only this record is left to review";
  }
  return queue.remaining === 1 ? "1 record to review" : `${queue.remaining} records to review`;
}

/** What the workspace says when the queue of records to review cannot be read. */
export const QUEUE_UNREADABLE_TEXT = "Could not load the records to review";
