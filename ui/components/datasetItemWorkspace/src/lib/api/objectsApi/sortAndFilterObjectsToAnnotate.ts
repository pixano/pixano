/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, WorkspaceType, type Annotation, type BBox } from "@pixano/core";

//Need to check, but it seems this function applies only to BBox
export const sortAndFilterObjectsToAnnotate = (
  objects: Annotation[],
  confidenceFilterValue: number[],
  currentFrameIndex: number,
): Annotation[] => {
  return objects
    .filter((object) => {
      if (object.ui.datasetItemType === WorkspaceType.IMAGE && object.is_type(BaseSchema.BBox)) {
        const confidence = (object as BBox).data.confidence || 0;
        return confidence >= confidenceFilterValue[0];
      }
      if (
        object.ui.datasetItemType === WorkspaceType.VIDEO &&
        object.is_type(BaseSchema.BBox) &&
        object.ui.frame_index === currentFrameIndex
      ) {
        const confidence = (object as BBox).data.confidence || 0;
        return confidence >= confidenceFilterValue[0];
      }
      return false; // Ignore objects without bboxes
    })
    .sort((a, b) => {
      const firstBoxXPosition = (a as BBox).data.coords[0] || 0;
      const secondBoxXPosition = (b as BBox).data.coords[0] || 0;
      return firstBoxXPosition - secondBoxXPosition;
    });
};
