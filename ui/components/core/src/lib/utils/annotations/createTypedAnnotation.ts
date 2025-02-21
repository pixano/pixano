/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  Annotation,
  BBox,
  Classification,
  Keypoints,
  Mask,
  Message,
  TextSpan,
  Tracklet,
  type AnnotationType,
  type BaseDataFields,
  type BBoxType,
  type ClassificationType,
  type KeypointsType,
  type MaskType,
  type MessageType,
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
  if (annotation.table_info.base_schema === BaseSchema.Classification) {
    return new Classification(annotation as unknown as BaseDataFields<ClassificationType>);
  }
  if (annotation.table_info.base_schema === BaseSchema.Keypoints) {
    return new Keypoints(annotation as unknown as BaseDataFields<KeypointsType>);
  }
  if (annotation.table_info.base_schema === BaseSchema.Mask) {
    return new Mask(annotation as unknown as BaseDataFields<MaskType>);
  }
  if (annotation.table_info.base_schema === BaseSchema.Message) {
    return new Message(annotation as unknown as BaseDataFields<MessageType>);
  }
  if (annotation.table_info.base_schema === BaseSchema.TextSpan) {
    return new TextSpan(annotation as unknown as BaseDataFields<TextSpanType>);
  }
  if (annotation.table_info.base_schema === BaseSchema.Tracklet) {
    return new Tracklet(annotation as unknown as BaseDataFields<TrackletType>);
  }
  console.error("createTypedAnnotation: No type found for annotation", annotation);
  return null;
};
