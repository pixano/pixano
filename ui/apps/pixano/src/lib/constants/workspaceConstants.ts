/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema } from "$lib/types/dataset";
import { ShapeType } from "$lib/types/shapeTypes";

// source ids
export const GROUND_TRUTH = "Ground Truth";
export const HUMAN = "User";
export const OTHER = "Unqualified";
export const MODEL_RUN = "Model Run";
export const PRE_ANNOTATION = "Pre-annotation";

export const EXISTING_SOURCE_IDS = [GROUND_TRUTH, PRE_ANNOTATION];

export const mapShapeType2BaseSchema: Partial<Record<ShapeType, BaseSchema>> = {
  [ShapeType.bbox]: BaseSchema.BBox,
  [ShapeType.keypoints]: BaseSchema.Keypoints,
  [ShapeType.mask]: BaseSchema.Mask,
  [ShapeType.polygon]: BaseSchema.MultiPath,
  [ShapeType.polyline]: BaseSchema.MultiPath,
  [ShapeType.track]: BaseSchema.Tracklet,
  [ShapeType.textSpan]: BaseSchema.TextSpan,
};

export const temporayTextSpanId = "temporaryHighlightedTextSpan_x45mqsw";

// PRE-ANNOTATION
export const HIGHLIGHTED_BOX_STROKE_FACTOR = 4;
export const HIGHLIGHTED_MASK_STROKE_FACTOR = 2;
export const NOT_ANNOTATION_ITEM_OPACITY = 0.3;
export const NEUTRAL_ENTITY_COLOR = "rgba(148, 163, 184, 0.55)";
export const PEEK_NEUTRAL_ENTITY_COLOR = "rgba(148, 163, 184, 0.95)";
export const PEEK_NEUTRAL_ANNOTATION_OPACITY = 0.65;
export const PEEK_NEUTRAL_MASK_OVERLAY_ALPHA = 0.4;
