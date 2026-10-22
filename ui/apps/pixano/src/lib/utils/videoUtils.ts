/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, Tracklet, type Annotation } from "$lib/types/dataset";

export const sortByFrameIndex = (a: Annotation, b: Annotation) => {
  if (a.is_type(BaseSchema.Tracklet) && b.is_type(BaseSchema.Tracklet)) {
    return (a as Tracklet).data.start_frame - (b as Tracklet).data.start_frame;
  } else {
    const indexA = a.ui.frame_index !== undefined ? a.ui.frame_index : Number.POSITIVE_INFINITY;
    const indexB = b.ui.frame_index !== undefined ? b.ui.frame_index : Number.POSITIVE_INFINITY;
    return indexA - indexB;
  }
};
