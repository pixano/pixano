/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BBox, Tracklet } from "@pixano/core";
import type { KeypointsTemplate, SaveItem, Annotation } from "@pixano/core";
import { nanoid } from "nanoid";

import { addOrUpdateSaveItem } from "./objectsApi";
import { saveData } from "../../lib/stores/datasetItemWorkspaceStores";

export const getCurrentImageTime = (imageIndex: number, videoSpeed: number) => {
  const currentTimestamp = imageIndex * videoSpeed;
  const minutes = Math.floor(currentTimestamp / 60000);
  const seconds = ((currentTimestamp % 60000) / 1000).toFixed(0);
  return `${minutes}:${Number(seconds) < 10 ? "0" : ""}${seconds}`;
};

export const getImageIndexFromMouseMove = (
  event: MouseEvent,
  node: HTMLButtonElement,
  length: number,
) => {
  const parentBounding = node.parentElement?.getBoundingClientRect();
  let left = event.clientX - (parentBounding?.left || 0);
  if (left < 0) left = 0;
  const max = node.parentElement?.offsetWidth || left;
  if (left > max) left = max;
  const index = Math.round((left / max) * length) - 1;
  return index < 0 ? 0 : index;
};

export const boxLinearInterpolation = (
  boxes: BBox[], //bboxes of the tracklet
  imageIndex: number,
  view_id: string,
): BBox | undefined => {
  //Note: this suppose boxes are sorted by frame_index (it should)
  const endIndex = boxes.findIndex((box) => box.frame_index >= imageIndex);
  if (endIndex < 0) {
    return undefined;
  }
  const endBox = boxes[endIndex];
  if (imageIndex == endBox.frame_index) {
    return endBox;
  }

  const startBox = boxes[endIndex - 1] || boxes[0];
  const [startX, startY, startWidth, startHeight] = startBox.data.coords;
  const [endX, endY, endWidth, endHeight] = endBox.data.coords;

  const xInterpolation = (endX - startX) / (endBox.frame_index - startBox.frame_index);
  const yInterpolation = (endY - startY) / (endBox.frame_index - startBox.frame_index);
  const widthInterpolation = (endWidth - startWidth) / (endBox.frame_index - startBox.frame_index);
  const heightInterpolation =
    (endHeight - startHeight) / (endBox.frame_index - startBox.frame_index);
  const x = startX + xInterpolation * (imageIndex - startBox.frame_index);
  const y = startY + yInterpolation * (imageIndex - startBox.frame_index);
  const width = startWidth + widthInterpolation * (imageIndex - startBox.frame_index);
  const height = startHeight + heightInterpolation * (imageIndex - startBox.frame_index);
  // make a new BBox with interpolated coords
  const interpolatedBox = structuredClone(startBox);
  interpolatedBox.id = nanoid(10);
  interpolatedBox.frame_index = imageIndex;
  interpolatedBox.data.view_ref.id = view_id;
  // for convenience, we store refs to start & end boxes
  interpolatedBox.startRef = startBox;
  interpolatedBox.endRef = endBox;
  interpolatedBox.data.coords = [x, y, width, height];
  return interpolatedBox;
};

export const keypointsLinearInterpolation = (
  keypoints: KeypointsTemplate[], //keypoints of the tracklet
  imageIndex: number,
  view_id: string,
): KeypointsTemplate | undefined => {
  //Note: this suppose keypoints are sorted by frame_index (it should)
  const endIndex = keypoints.findIndex((kpt) => kpt.frame_index >= imageIndex);
  if (endIndex < 0) {
    return undefined;
  }
  const endKpt = keypoints[endIndex];
  if (imageIndex == endKpt.frame_index) {
    return endKpt;
  }
  const startKpt = keypoints[endIndex - 1] || keypoints[0];
  if (endKpt.frame_index == startKpt?.frame_index) {
    return startKpt;
  } else {
    const vertices = startKpt.vertices.map((vertex, i) => {
      const xInterpolation =
        (endKpt.vertices[i].x - vertex.x) / (endKpt.frame_index - startKpt?.frame_index);
      const yInterpolation =
        (endKpt.vertices[i].y - vertex.y) / (endKpt.frame_index - startKpt?.frame_index);
      const x = vertex.x + xInterpolation * (imageIndex - startKpt.frame_index);
      const y = vertex.y + yInterpolation * (imageIndex - startKpt.frame_index);
      return { ...vertex, x, y };
    });
    // make a new BBox with interpolated coords
    const interpolatedKpt = structuredClone(startKpt);
    interpolatedKpt.id = nanoid(5); //not needed but it still ensure unique id
    interpolatedKpt.frame_index = imageIndex;
    interpolatedKpt.viewRef.id = view_id;
    // for convenience, we store refs to start & end kpts
    interpolatedKpt.startRef = startKpt;
    interpolatedKpt.endRef = endKpt;
    interpolatedKpt.vertices = vertices;
    return interpolatedKpt;
  }
};

export const splitTrackletInTwo = (
  tracklet2split: Tracklet,
  prev: number,
  next: number,
): { left: Annotation; right: Annotation } => {
  const rightTrackletOrig = structuredClone(tracklet2split);
  const {
    datasetItemType,
    displayControl,
    highlighted,
    frame_index,
    review_state,
    childs,
    ...noUIfieldsTracklet
  } = rightTrackletOrig;
  const rightTracklet = new Tracklet(noUIfieldsTracklet);
  rightTracklet.id = nanoid(10);
  rightTracklet.data.start_timestep = next;
  rightTracklet.childs = childs.filter((ann) => ann.frame_index >= next);
  rightTracklet.datasetItemType = datasetItemType;
  rightTracklet.displayControl = displayControl;
  rightTracklet.highlighted = highlighted;
  rightTracklet.frame_index = frame_index;
  rightTracklet.review_state = review_state;

  //tracklet2split become left tracklet
  tracklet2split.data.end_timestep = prev;
  tracklet2split.childs = tracklet2split.childs.filter((ann) => ann.frame_index <= prev);

  const save_item_left: SaveItem = {
    change_type: "update",
    object: tracklet2split,
  };
  saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_left));
  const save_item_right: SaveItem = {
    change_type: "add",
    object: rightTracklet,
  };
  saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_right));
  return { left: tracklet2split, right: rightTracklet };
};

export const filterTrackletItems = (
  newFrameIndex: number,
  draggedFrameIndex: number,
  tracklet: Tracklet,
): { tracklet: Tracklet; item: Annotation; resized: boolean } => {
  const isGoingRight = newFrameIndex > draggedFrameIndex;
  const isStart = draggedFrameIndex === tracklet.data.start_timestep;
  const isEnd = draggedFrameIndex === tracklet.data.end_timestep;

  tracklet.childs = tracklet.childs.filter((ann) => {
    if (isGoingRight && ann.frame_index > draggedFrameIndex && ann.frame_index < newFrameIndex) {
      return false;
    }
    if (!isGoingRight && ann.frame_index > newFrameIndex && ann.frame_index < draggedFrameIndex) {
      return false;
    }
    return true;
  });
  if (isStart) {
    tracklet.data.start_timestep = newFrameIndex;
    tracklet.childs[0].frame_index = newFrameIndex;
    return tracklet;
  }
  if (isEnd) {
    tracklet.data.end_timestep = newFrameIndex;
    tracklet.childs[tracklet.childs.length - 1].frame_index = newFrameIndex;
    return tracklet;
  }
  tracklet.childs = tracklet.childs.map((ann) => {
    if (ann.frame_index === draggedFrameIndex) {
      ann.frame_index = newFrameIndex;
      return ann;
    }
    return ann;
  });
  if (newFrameIndex < tracklet.data.start_timestep) {
    tracklet.data.start_timestep = newFrameIndex;
  }
  if (newFrameIndex > tracklet.data.end_timestep) {
    tracklet.data.end_timestep = newFrameIndex;
  }
  return tracklet;
};

export const sortByFrameIndex = (a: Annotation, b: Annotation) => {
  if (a.is_tracklet && b.is_tracklet) {
    return (a as Tracklet).data.start_timestep - (b as Tracklet).data.start_timestep;
  } else {
    const indexA = a.frame_index !== undefined ? a.frame_index : Number.POSITIVE_INFINITY;
    const indexB = b.frame_index !== undefined ? b.frame_index : Number.POSITIVE_INFINITY;
    return indexA - indexB;
  }
};
