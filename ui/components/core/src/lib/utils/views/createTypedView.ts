/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  Image,
  SequenceFrame,
  sequenceFrameSchema,
  type BaseDataFields,
  type ImageType,
  type SequenceFrameType,
  type ViewType,
} from "../../types";

export const createTypedView = (view: BaseDataFields<ViewType> | BaseDataFields<ViewType>[]) => {
  if (Array.isArray(view)) {
    const isSequenceFrame = sequenceFrameSchema.array().safeParse(view.map((v) => v.data)).success;

    if (isSequenceFrame) {
      const sequenceFrames: SequenceFrame[] = [];
      for (const v of view) {
        sequenceFrames.push(new SequenceFrame(v as unknown as BaseDataFields<SequenceFrameType>));
      }
      return sequenceFrames;
    } else {
      const images: Image[] = [];
      for (const v of view) {
        images.push(new Image(v as unknown as BaseDataFields<ImageType>));
      }
      return images;
    }
  }

  return new Image(view as unknown as BaseDataFields<ImageType>);
};
