/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, Tracklet, type Annotation } from "$lib/types/dataset";

export const getCurrentImageTime = (imageIndex: number, videoSpeed: number) => {
  const date = new Date(imageIndex * videoSpeed);
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");
  const milliseconds = String(date.getMilliseconds()).padStart(3, "0");
  return `${minutes}:${seconds}.${milliseconds}`;
};

export const getImageIndexFromMouseMove = (
  event: MouseEvent,
  node: HTMLButtonElement,
  length: number,
) => {
  const parentBounding = node.parentElement?.getBoundingClientRect();
  let left = event.clientX - (parentBounding?.left || 0);
  if (left <0) left = 0;
  const max = node.parentElement?.offsetWidth || left;
  if (left > max) left = max;
  const index = Math.round((left / max) * length) - 1;
  return index <0 ? 0 : index;
};

export const sortByFrameIndex = (a: Annotation, b: Annotation) => {
  if (a.is_type(BaseSchema.Tracklet) && b.is_type(BaseSchema.Tracklet)) {
    return (a as Tracklet).data.start_frame - (b as Tracklet).data.start_frame;
  } else {
    const indexA = a.ui.frame_index !== undefined ? a.ui.frame_index : Number.POSITIVE_INFINITY;
    const indexB = b.ui.frame_index !== undefined ? b.ui.frame_index : Number.POSITIVE_INFINITY;
    return indexA - indexB;
  }
};
