/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { buildQueryString, requestJson } from "./apiClient";
import type { NextRecordToReview } from "./restTypes";
import { REVIEW_STATUS } from "$lib/constants/reviewConstants";

/**
 * The next record holding a model's annotation still to review.
 *
 * @param datasetId The dataset under review.
 * @param after The record the reviewer is leaving, if any.
 */
export async function getNextRecordToReview(
  datasetId: string,
  after?: string,
): Promise<NextRecordToReview> {
  const query = buildQueryString({ status: REVIEW_STATUS.PENDING, after });
  return requestJson<NextRecordToReview>(
    `/datasets/${datasetId}/review/next${query}`,
    {},
    "getNextRecordToReview",
  );
}
