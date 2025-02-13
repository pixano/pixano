/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, type Mask } from "@pixano/core";
import { mask_utils } from "@pixano/models";

import {
  HIGHLIGHTED_MASK_STROKE_FACTOR,
  NOT_ANNOTATION_ITEM_OPACITY,
  PRE_ANNOTATION,
} from "../../constants";

export const mapObjectToMasks = (obj: Mask): Mask | undefined => {
  if (
    obj.is_type(BaseSchema.Mask) &&
    obj.data.view_ref.name &&
    !obj.ui.review_state &&
    !(obj.data.source_ref.name === PRE_ANNOTATION && obj.ui.review_state === "accepted")
  ) {
    const rle = obj.data.counts as number[];
    const size = obj.data.size;
    const maskPoly = mask_utils.generatePolygonSegments(rle, size[0]);
    const masksSVG = mask_utils.convertSegmentsToSVG(maskPoly);

    return {
      id: obj.id,
      data: obj.data,
      ui: {
        ...obj.ui,
        svg: masksSVG,
        opacity: obj.ui.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
        strokeFactor: obj.ui.highlighted === "self" ? HIGHLIGHTED_MASK_STROKE_FACTOR : 1,
      },
    } as Mask;
  }
  return undefined;
};
