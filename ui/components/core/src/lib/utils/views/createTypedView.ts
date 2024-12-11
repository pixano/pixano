/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  Image,
  SequenceFrame,
  type BaseDataFields,
  type ImageType,
  type SequenceFrameType,
  type ViewType,
} from "../../types";

export const createTypedView = (view: BaseDataFields<ViewType>) => {
  if (Array.isArray(view)) {
    const sequenceFrames: SequenceFrame[] = [];
    for (const v of view) {
      sequenceFrames.push(new SequenceFrame(v as unknown as BaseDataFields<SequenceFrameType>));
    }
    return sequenceFrames;
  }

  return new Image(view as unknown as BaseDataFields<ImageType>);
};
