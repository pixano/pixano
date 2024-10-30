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
  const endIndex = boxes.findIndex((box) => box.ui.frame_index! >= imageIndex);
  if (endIndex < 0) {
    return undefined;
  }
  const endBox = boxes[endIndex];
  if (imageIndex === endBox.ui.frame_index) {
    return endBox;
  }
  const startBox = boxes[endIndex - 1] || boxes[0];
  if (startBox.ui.frame_index! > imageIndex || endBox.ui.frame_index! < imageIndex)
    return undefined;
  const [startX, startY, startWidth, startHeight] = startBox.data.coords;
  const [endX, endY, endWidth, endHeight] = endBox.data.coords;

  const xInterpolation = (endX - startX) / (endBox.ui.frame_index! - startBox.ui.frame_index!);
  const yInterpolation = (endY - startY) / (endBox.ui.frame_index! - startBox.ui.frame_index!);
  const widthInterpolation =
    (endWidth - startWidth) / (endBox.ui.frame_index! - startBox.ui.frame_index!);
  const heightInterpolation =
    (endHeight - startHeight) / (endBox.ui.frame_index! - startBox.ui.frame_index!);
  const x = startX + xInterpolation * (imageIndex - startBox.ui.frame_index!);
  const y = startY + yInterpolation * (imageIndex - startBox.ui.frame_index!);
  const width = startWidth + widthInterpolation * (imageIndex - startBox.ui.frame_index!);
  const height = startHeight + heightInterpolation * (imageIndex - startBox.ui.frame_index!);
  // make a new BBox with interpolated coords
  const { ui, ...noUIfieldsBBox } = structuredClone(startBox);
  const interpolatedBox = new BBox(noUIfieldsBBox);
  interpolatedBox.ui = ui;
  interpolatedBox.id = nanoid(10);
  interpolatedBox.ui.frame_index = imageIndex;
  interpolatedBox.data.view_ref.id = view_id;
  // for convenience, we store ref to start boxes
  interpolatedBox.ui.startRef = startBox;
  // top_entity (if exist) lost class with structuredClone: remove it
  if (interpolatedBox.ui.top_entity) interpolatedBox.ui.top_entity = undefined;
  interpolatedBox.data.coords = [x, y, width, height];
  console.log("IB", interpolatedBox);
  return interpolatedBox;
};

export const keypointsLinearInterpolation = (
  keypoints: KeypointsTemplate[], //keypoints of the tracklet
  imageIndex: number,
  view_id: string,
): KeypointsTemplate | undefined => {
  //Note: this suppose keypoints are sorted by frame_index (it should)
  const endIndex = keypoints.findIndex((kpt) => kpt.frame_index! >= imageIndex);
  if (endIndex < 0) {
    return undefined;
  }
  const endKpt = keypoints[endIndex];
  if (imageIndex == endKpt.frame_index) {
    return endKpt;
  }
  const startKpt = keypoints[endIndex - 1] || keypoints[0];
  if (startKpt.frame_index! > imageIndex || endKpt.frame_index! < imageIndex) return undefined;
  if (endKpt.frame_index == startKpt.frame_index) {
    return startKpt;
  } else {
    const vertices = startKpt.vertices.map((vertex, i) => {
      const xInterpolation =
        (endKpt.vertices[i].x - vertex.x) / (endKpt.frame_index! - startKpt.frame_index!);
      const yInterpolation =
        (endKpt.vertices[i].y - vertex.y) / (endKpt.frame_index! - startKpt.frame_index!);
      const x = vertex.x + xInterpolation * (imageIndex - startKpt.frame_index!);
      const y = vertex.y + yInterpolation * (imageIndex - startKpt.frame_index!);
      return { ...vertex, x, y };
    });
    // make a new KeypointsTemplate with interpolated coords
    const interpolatedKpt = structuredClone(startKpt);
    interpolatedKpt.id = nanoid(5); //not needed but it still ensure unique id
    interpolatedKpt.frame_index = imageIndex;
    interpolatedKpt.viewRef = { id: view_id, name: startKpt.viewRef?.name || "" }; //for lint
    // for convenience, we store ref to start kpts
    interpolatedKpt.startRef = startKpt;
    // top_entity (if exist) lost class with structuredClone: remove it
    if (interpolatedKpt.top_entity) interpolatedKpt.top_entity = undefined;
    interpolatedKpt.vertices = vertices;
    return interpolatedKpt;
  }
};

export const splitTrackletInTwo = (
  tracklet2split: Tracklet,
  prev: number,
  next: number,
): Annotation => {
  const rightTrackletOrig = structuredClone(tracklet2split);
  const { ui, ...noUIfieldsTracklet } = rightTrackletOrig;
  const rightTracklet = new Tracklet(noUIfieldsTracklet);
  rightTracklet.id = nanoid(10);
  rightTracklet.data.start_timestep = next;
  rightTracklet.ui = ui;
  //note: get object links from original object, as structuredClone lose class specifics
  rightTracklet.ui.childs = tracklet2split.ui.childs.filter((ann) => ann.ui.frame_index! >= next);
  rightTracklet.ui.top_entity = tracklet2split.ui.top_entity;
  console.log("splitR", rightTracklet);
  //tracklet2split become left tracklet
  tracklet2split.data.end_timestep = prev;
  tracklet2split.ui.childs = tracklet2split.ui.childs.filter((ann) => ann.ui.frame_index! <= prev);

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
  return rightTracklet;
};

export const sortByFrameIndex = (a: Annotation, b: Annotation) => {
  if (a.is_tracklet && b.is_tracklet) {
    return (a as Tracklet).data.start_timestep - (b as Tracklet).data.start_timestep;
  } else {
    const indexA = a.ui.frame_index !== undefined ? a.ui.frame_index : Number.POSITIVE_INFINITY;
    const indexB = b.ui.frame_index !== undefined ? b.ui.frame_index : Number.POSITIVE_INFINITY;
    return indexA - indexB;
  }
};
