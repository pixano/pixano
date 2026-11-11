/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// The review's vocabulary, the backend's (`ReviewStatus` in
// src/pixano/schemas/annotations/entity_annotation.py). It imports nothing, so that the routes and
// the API client can read it without loading the domain model.

export const REVIEW_STATUS = {
  PENDING: "pending",
  ACCEPTED: "accepted",
} as const;

export type ReviewStatus = (typeof REVIEW_STATUS)[keyof typeof REVIEW_STATUS];

/** The column that holds a row's review status, and the field an Accept sends. */
export const REVIEW_STATUS_FIELD = "review_status";

/** The `source_type` of a model's row: the only rows that are reviewed. */
export const MODEL_SOURCE_TYPE = "model";
