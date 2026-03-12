/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { nanoid } from "nanoid";

import { BBox } from "$lib/types/dataset";
import type { KeypointAnnotation } from "$lib/types/shapeTypes";

import { HIGHLIGHTED_BOX_STROKE_FACTOR, NOT_ANNOTATION_ITEM_OPACITY } from "$lib/constants/workspaceConstants";

export const boxLinearInterpolation = (
  boxes: BBox[], //bboxes of the tracklet
  imageIndex: number,
  view_id: string,
): BBox | undefined => {
  //Note: this suppose boxes are sorted by frame_index (it should)
  const endIndex = boxes.findIndex((box) => box.ui.frame_index >= imageIndex);
  if (endIndex <0) {
    return undefined;
  }
  const endBox = boxes[endIndex];
  if (imageIndex === endBox.ui.frame_index) {
    return endBox;
  }
  const startBox = boxes[endIndex - 1] || boxes[0];
  if (startBox.ui.frame_index > imageIndex || endBox.ui.frame_index <imageIndex)
    return undefined;
  const [startX, startY, startWidth, startHeight] = startBox.data.coords;
  const [endX, endY, endWidth, endHeight] = endBox.data.coords;

  const xInterpolation = (endX - startX) / (endBox.ui.frame_index - startBox.ui.frame_index);
  const yInterpolation = (endY - startY) / (endBox.ui.frame_index - startBox.ui.frame_index);
  const widthInterpolation =
    (endWidth - startWidth) / (endBox.ui.frame_index - startBox.ui.frame_index);
  const heightInterpolation =
    (endHeight - startHeight) / (endBox.ui.frame_index - startBox.ui.frame_index);
  const x = startX + xInterpolation * (imageIndex - startBox.ui.frame_index);
  const y = startY + yInterpolation * (imageIndex - startBox.ui.frame_index);
  const width = startWidth + widthInterpolation * (imageIndex - startBox.ui.frame_index);
  const height = startHeight + heightInterpolation * (imageIndex - startBox.ui.frame_index);
  // make a new BBox with interpolated coords
  const { ui, ...noUIfieldsBBox } = structuredClone(startBox);
  const interpolatedBox = new BBox(noUIfieldsBBox);
  interpolatedBox.ui = ui;
  interpolatedBox.id = nanoid(10);
  interpolatedBox.ui.frame_index = imageIndex;
  interpolatedBox.ui.displayControl = {
    hidden: startBox.ui.displayControl.hidden,
    editing: false,
    //if editing, we highlight only current frame object, else we keep hihlighted status of startRef
    highlighted: startBox.ui.displayControl.editing
      ? "none"
      : startBox.ui.displayControl.highlighted,
  };
  interpolatedBox.data.frame_id = view_id;
  //we also need to adapt opacity & strokeFactor accordingly
  interpolatedBox.ui.opacity =
    interpolatedBox.ui.displayControl.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0;
  interpolatedBox.ui.strokeFactor =
    interpolatedBox.ui.displayControl.highlighted === "self" ? HIGHLIGHTED_BOX_STROKE_FACTOR : 1;
  // for convenience, we store ref to start boxes
  interpolatedBox.ui.startRef = startBox;
  // top_entities (if exist) lost class with structuredClone: replace it
  interpolatedBox.ui.top_entities = startBox.ui.top_entities;
  interpolatedBox.data.coords = [x, y, width, height];
  return interpolatedBox;
};

export const keypointsLinearInterpolation = (
  keypoints: KeypointAnnotation[], //keypoints of the tracklet
  imageIndex: number,
  view_id: string,
): KeypointAnnotation | undefined => {
  //Note: this suppose keypoints are sorted by frame_index (it should)
  const endIndex = keypoints.findIndex((kpt) => kpt.ui.frame_index >= imageIndex);
  if (endIndex <0) {
    return undefined;
  }
  const endKpt = keypoints[endIndex];
  if (imageIndex == endKpt.ui.frame_index) {
    return endKpt;
  }
  const startKpt = keypoints[endIndex - 1] || keypoints[0];
  if (startKpt.ui.frame_index > imageIndex || endKpt.ui.frame_index <imageIndex)
    return undefined;
  if (endKpt.ui.frame_index === startKpt.ui.frame_index) {
    return startKpt;
  } else {
    const startVertices = startKpt.graph.vertices;
    const endVertices = endKpt.graph.vertices;
    const vertices = startVertices.map((vertex, i) => {
      const xInterpolation =
        (endVertices[i].x - vertex.x) / (endKpt.ui.frame_index - startKpt.ui.frame_index);
      const yInterpolation =
        (endVertices[i].y - vertex.y) / (endKpt.ui.frame_index - startKpt.ui.frame_index);
      const x = vertex.x + xInterpolation * (imageIndex - startKpt.ui.frame_index);
      const y = vertex.y + yInterpolation * (imageIndex - startKpt.ui.frame_index);
      return { x, y };
    });
    // make a new KeypointAnnotation with interpolated coords
    const interpolatedKpt = structuredClone(startKpt);
    interpolatedKpt.id = nanoid(5); //not needed but it still ensure unique id
    interpolatedKpt.ui.frame_index = imageIndex;
    interpolatedKpt.ui.displayControl = {
      hidden: startKpt.ui.displayControl.hidden,
      editing: false,
      //if editing, we highlight only current frame object, else we keep hihlighted status of startRef
      highlighted: startKpt.ui.displayControl.editing
        ? "none"
        : startKpt.ui.displayControl.highlighted,
    };
    interpolatedKpt.viewRef = { id: view_id, name: startKpt.viewRef?.name || "" }; //for lint
    // for convenience, we store ref to start kpts
    interpolatedKpt.ui.startRef = startKpt;
    // top_entities (if exist) lost class with structuredClone: replace it
    interpolatedKpt.ui.top_entities = startKpt.ui.top_entities;
    interpolatedKpt.graph = { ...startKpt.graph, vertices };
    return interpolatedKpt;
  }
};
