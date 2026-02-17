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
    const metadata = obj.data.inference_metadata as Record<string, unknown>;
    const metadataPolygonSvg = metadata.polygon_svg;
    const metadataPolygonPoints = metadata.polygon_points;
    const isPolygonSvg =
      metadata.geometry_mode === "polygon" &&
      Array.isArray(metadataPolygonSvg) &&
      metadataPolygonSvg.every((value) => typeof value === "string");
    const isPolygonPoints =
      metadata.geometry_mode === "polygon" &&
      Array.isArray(metadataPolygonPoints) &&
      metadataPolygonPoints.every(
        (polygon) =>
          Array.isArray(polygon) &&
          polygon.every(
            (point) =>
              typeof point === "object" &&
              point !== null &&
              "x" in point &&
              "y" in point &&
              "id" in point,
          ),
      );

    const masksSVG = isPolygonSvg
      ? metadataPolygonSvg
      : (() => {
          const rle = obj.data.counts as number[];
          const size = obj.data.size;
          const maskPoly = mask_utils.generatePolygonSegments(rle, size[0]);
          return mask_utils.convertSegmentsToSVG(maskPoly);
        })();

    return {
      id: obj.id,
      data: obj.data,
      ui: {
        ...obj.ui,
        svg: masksSVG,
        ...(isPolygonPoints ? { rawPoints: metadataPolygonPoints } : {}),
        opacity: obj.ui.displayControl.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
        strokeFactor:
          obj.ui.displayControl.highlighted === "self" ? HIGHLIGHTED_MASK_STROKE_FACTOR : 1,
      },
    } as Mask;
  }
  return undefined;
};
