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
  MultiPath,
  TextSpan,
  Tracklet,
  BaseSchema,
  Entity,
  Image,
  SequenceFrame,
  TextView,
  type RawSchemaData,
} from "$lib/types/dataset";

export const createTypedAnnotation = (
  annotation: RawSchemaData,
): Annotation | null => {
  if (annotation.table_info.base_schema === BaseSchema.BBox) {
    return new BBox(annotation);
  }
  if (annotation.table_info.base_schema === BaseSchema.Classification) {
    return new Classification(annotation);
  }
  if (annotation.table_info.base_schema === BaseSchema.Keypoints) {
    return new Keypoints(annotation);
  }
  if (annotation.table_info.base_schema === BaseSchema.Mask) {
    return new Mask(annotation);
  }
  if (annotation.table_info.base_schema === BaseSchema.MultiPath) {
    return new MultiPath(annotation);
  }
  if (annotation.table_info.base_schema === BaseSchema.Message) {
    return new Message(annotation);
  }
  if (annotation.table_info.base_schema === BaseSchema.TextSpan) {
    return new TextSpan(annotation);
  }
  if (annotation.table_info.base_schema === BaseSchema.Tracklet) {
    return new Tracklet(annotation);
  }
  console.error("createTypedAnnotation: No type found for annotation", annotation);
  return null;
};

export const createTypedEntity = (entity: RawSchemaData) => {
  return new Entity(entity);
};

export const createTypedView = (view: RawSchemaData | RawSchemaData[]) => {
  if (Array.isArray(view)) {
    const isSequenceFrame = view.every(
      (v) => "frame_index" in (v.data as Record<string, unknown>) && "timestamp" in (v.data as Record<string, unknown>),
    );

    if (isSequenceFrame) {
      const sequenceFrames: SequenceFrame[] = [];
      for (const v of view) {
        sequenceFrames.push(new SequenceFrame(v));
      }
      return sequenceFrames;
    } else {
      const images: Image[] = [];
      for (const v of view) {
        images.push(new Image(v));
      }
      return images;
    }
  } else if (view.table_info.base_schema === BaseSchema.TextView) {
    return new TextView(view);
  }
  return new Image(view);
};
