import {
  Annotation,
  BBox,
  Keypoints,
  Mask,
  Tracklet,
  type AnnotationType,
  type BaseDataFields,
  type BBoxType,
  type KeypointsType,
  type MaskType,
  type TrackletType,
} from "../../types";

export const createTypedAnnotation = (
  annotation: BaseDataFields<AnnotationType>,
): Annotation | null => {
  if (annotation.table_info.base_schema === "BBox") {
    return new BBox(annotation as unknown as BaseDataFields<BBoxType>);
  }
  if (annotation.table_info.base_schema === "KeyPoints") {
    return new Keypoints(annotation as unknown as BaseDataFields<KeypointsType>);
  }
  if (annotation.table_info.base_schema === "CompressedRLE") {
    return new Mask(annotation as unknown as BaseDataFields<MaskType>);
  }
  if (annotation.table_info.base_schema === "Tracklet") {
    return new Tracklet(annotation as unknown as BaseDataFields<TrackletType>);
  }
  console.error("createTypedAnnotation: No type found for annotation", annotation);
  return null;
};
