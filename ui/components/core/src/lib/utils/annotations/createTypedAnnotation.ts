/* eslint-disable @typescript-eslint/no-unsafe-enum-comparison */

/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/


import {
  Annotation,
  BBox,
  Keypoints,
  Mask,
  BaseTextSpan,
  Tracklet,
  type AnnotationType,
  type BaseDataFields,
  type BBoxType,
  type KeypointsType,
  type MaskType,
  type TextSpanType,
  type TrackletType,
} from "../../types";
import { BaseSchema } from "../../types/dataset/BaseSchema";

export const createTypedAnnotation = (
  annotation: BaseDataFields<AnnotationType>,
): Annotation | null => {
  if (annotation.table_info.base_schema === BaseSchema.BBox) {
    return new BBox(annotation as unknown as BaseDataFields<BBoxType>);
  }
  if (annotation.table_info.base_schema === BaseSchema.Keypoints) {
    return new Keypoints(annotation as unknown as BaseDataFields<KeypointsType>);
  }
  if (annotation.table_info.base_schema === BaseSchema.Mask) {
    return new Mask(annotation as unknown as BaseDataFields<MaskType>);
  }
  if (annotation.table_info.base_schema === BaseSchema.Tracklet) {
    return new Tracklet(annotation as unknown as BaseDataFields<TrackletType>);
  }
  if (annotation.table_info.base_schema === BaseSchema.TextSpan) {
    return new BaseTextSpan(annotation as unknown as BaseDataFields<TextSpanType>);
  }
  console.error("createTypedAnnotation: No type found for annotation", annotation);
  return null;
};
