/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, type SaveShapeType } from "@pixano/core";

// source ids
export const GROUND_TRUTH = "Ground Truth";
export const HUMAN = "User";
export const OTHER = "Unqualified";
export const MODEL_RUN = "Model Run";
export const PRE_ANNOTATION = "Pre-annotation";

export const EXISTING_SOURCE_IDS = [GROUND_TRUTH, PRE_ANNOTATION];

export const mapShapeType2BaseSchema: Record<SaveShapeType, BaseSchema> = {
  bbox: BaseSchema.BBox,
  keypoints: BaseSchema.Keypoints,
  mask: BaseSchema.Mask,
  tracklet: BaseSchema.Tracklet,
  textSpan: BaseSchema.TextSpan,
};

// PRE-ANNOTATION
export const HIGHLIGHTED_BOX_STROKE_FACTOR = 4;
export const HIGHLIGHTED_MASK_STROKE_FACTOR = 2;
export const NOT_ANNOTATION_ITEM_OPACITY = 0.3;
