/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Payload of a media-level classification — "this image is a beach scene".
 *
 * It sits in the `geometry` slot of `LocalAnnotation` like every other kind,
 * but there is nothing spatial about it: a classification annotates the whole
 * view, not a region of it. The slot is the per-kind payload, and this kind's
 * payload happens to be a label list.
 *
 * Invariant the backend enforces and the seed loader re-checks: one confidence
 * per label.
 */
export interface ClassificationGeometry {
  /** Class names asserted for the view. */
  labels: string[];
  /** One confidence per label; 1 for anything a human asserted. */
  confidences: number[];
}

/** Confidence recorded for a label a person chose, as opposed to a model. */
export const HUMAN_CONFIDENCE = 1;

/** Konva node name for a classification chip, shared with the tests. */
export const CLASSIFICATION_NODE_NAME = "pixano-classification";

/** Attribute carrying the local annotation id on a classification chip. */
export const CLASSIFICATION_ID_ATTR = "pixanoClassificationId";

/** Tool id, referenced by the toolbar and by tests. */
export const CLASSIFY_TOOL_ID = "classify";
