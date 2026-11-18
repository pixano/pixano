/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { JSON_HEADERS, requestJson } from "./apiClient";

/** What `GET /datasets/{id}/review/next` answers (src/pixano/api/routers/review.py). */
export interface NextRecordToReviewResponse {
  /** The next record holding annotations of the asked status, or null when none does. */
  record_id: string | null;
  /** How many records hold annotations of that status. */
  remaining: number;
}

export interface NextRecordToReviewParams {
  /** A review status: `pending` or `accepted`. */
  status: string;
  /** The record to start after, in record-id order; the server wraps round. */
  after?: string | null;
}

/**
 * Find the next record holding annotations of a review status, whatever their
 * kind — the server scans every entity-annotation table, so no kind is named
 * here.
 */
export function getNextRecordToReview(
  datasetId: string,
  params: NextRecordToReviewParams,
): Promise<NextRecordToReviewResponse> {
  const qs = new URLSearchParams({ status: params.status });
  if (params.after) qs.set("after", params.after);
  return requestJson<NextRecordToReviewResponse>(
    `/datasets/${datasetId}/review/next?${qs.toString()}`,
    { headers: JSON_HEADERS, method: "GET" },
    "getNextRecordToReview",
  );
}
