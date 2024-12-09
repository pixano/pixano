/* eslint-disable @typescript-eslint/no-unsafe-enum-comparison */
import {
  Annotation,
  BBox,
  Keypoints,
  Mask,
  NamedEntity,
  Tracklet,
  type AnnotationType,
  type BaseDataFields,
  type BBoxType,
  type KeypointsType,
  type MaskType,
  type NamedEntityType,
  type TrackletType,
} from "../../types";
import { AnnotationBaseSchema } from "../../types/dataset/annotations/AnnotationBaseSchema";

export const createTypedAnnotation = (
  annotation: BaseDataFields<AnnotationType>,
): Annotation | null => {
  if (annotation.table_info.base_schema === AnnotationBaseSchema.BBox) {
    return new BBox(annotation as unknown as BaseDataFields<BBoxType>);
  }
  if (annotation.table_info.base_schema === AnnotationBaseSchema.Keypoints) {
    return new Keypoints(annotation as unknown as BaseDataFields<KeypointsType>);
  }
  if (annotation.table_info.base_schema === AnnotationBaseSchema.Mask) {
    return new Mask(annotation as unknown as BaseDataFields<MaskType>);
  }
  if (annotation.table_info.base_schema === AnnotationBaseSchema.Tracklet) {
    return new Tracklet(annotation as unknown as BaseDataFields<TrackletType>);
  }
  if (annotation.table_info.base_schema === AnnotationBaseSchema.NamedEntity) {
    return new NamedEntity(annotation as unknown as BaseDataFields<NamedEntityType>);
  }
  console.error("createTypedAnnotation: No type found for annotation", annotation);
  return null;
};
