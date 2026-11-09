/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ReviewStatus } from "$lib/annotations/reviewStatus.js";
import { getNextRecordToReview } from "$lib/api/review.js";

/** The next record to review, as the workspace reads it. */
export interface NextRecordToReview {
  /** Null when no record holds annotations of the asked status. */
  recordId: string | null;
  /** How many records hold annotations of that status. */
  remaining: number;
}

/**
 * The I/O the review queue needs, and nothing else. Kept apart from
 * `DatasetGateway` so the review feature widens no existing contract — the
 * loader, the queue and their fakes never see it.
 */
export interface ReviewGateway {
  nextRecordToReview(
    datasetId: string,
    query: { status: ReviewStatus; after: string | null },
  ): Promise<NextRecordToReview>;
}

/** Production gateway: a thin pass-through to the HTTP module (`$lib/api/review`). */
export const httpReviewGateway: ReviewGateway = {
  nextRecordToReview: async (datasetId, { status, after }) => {
    const response = await getNextRecordToReview(datasetId, { status, after });
    return { recordId: response.record_id, remaining: response.remaining };
  },
};
