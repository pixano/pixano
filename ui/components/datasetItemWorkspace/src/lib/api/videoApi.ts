/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { nanoid } from "nanoid";
import { get } from "svelte/store";

import type { Annotation, KeypointsTemplate, SaveItem } from "@pixano/core";
import { BaseSchema, BBox, Tracklet } from "@pixano/core";

import { sourcesStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
import { saveData } from "../../lib/stores/datasetItemWorkspaceStores";
import {
  imagesFilesUrlsByFrame,
  imagesPerView,
  imagesPerViewBuffer,
  lastFrameIndex,
} from "../../lib/stores/videoViewerStores";
import { HIGHLIGHTED_BOX_STROKE_FACTOR, NOT_ANNOTATION_ITEM_OPACITY } from "../constants";
import { addOrUpdateSaveItem, getPixanoSource } from "./objectsApi";

let timerId: ReturnType<typeof setTimeout>;
// buffer
const ratioOfBackwardBuffer = 0.1;
const bufferSize = 200;
let previousCount: number = 0;
let nextCount: number = 0;

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
  interpolatedBox.ui.displayControl = {
    hidden: startBox.ui.displayControl?.hidden,
    editing: false,
  };
  //if editing, we highlight only current frame object, else we keep hihlighted status of startRef
  interpolatedBox.ui.highlighted = startBox.ui.displayControl?.editing
    ? "none"
    : startBox.ui.highlighted;
  interpolatedBox.data.view_ref.id = view_id;
  //we also need to adapt opacity & strokeFactor accordingly
  interpolatedBox.ui.opacity =
    interpolatedBox.ui.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0;
  interpolatedBox.ui.strokeFactor =
    interpolatedBox.ui.highlighted === "self" ? HIGHLIGHTED_BOX_STROKE_FACTOR : 1;
  // for convenience, we store ref to start boxes
  interpolatedBox.ui.startRef = startBox;
  // top_entities (if exist) lost class with structuredClone: replace it
  interpolatedBox.ui.top_entities = startBox.ui.top_entities;
  interpolatedBox.data.coords = [x, y, width, height];
  return interpolatedBox;
};

export const keypointsLinearInterpolation = (
  keypoints: KeypointsTemplate[], //keypoints of the tracklet
  imageIndex: number,
  view_id: string,
): KeypointsTemplate | undefined => {
  //Note: this suppose keypoints are sorted by frame_index (it should)
  const endIndex = keypoints.findIndex((kpt) => kpt.ui!.frame_index! >= imageIndex);
  if (endIndex < 0) {
    return undefined;
  }
  const endKpt = keypoints[endIndex];
  if (imageIndex == endKpt.ui!.frame_index) {
    return endKpt;
  }
  const startKpt = keypoints[endIndex - 1] || keypoints[0];
  if (startKpt.ui!.frame_index! > imageIndex || endKpt.ui!.frame_index! < imageIndex)
    return undefined;
  if (endKpt.ui!.frame_index === startKpt.ui!.frame_index) {
    return startKpt;
  } else {
    const vertices = startKpt.vertices.map((vertex, i) => {
      const xInterpolation =
        (endKpt.vertices[i].x - vertex.x) / (endKpt.ui!.frame_index! - startKpt.ui!.frame_index!);
      const yInterpolation =
        (endKpt.vertices[i].y - vertex.y) / (endKpt.ui!.frame_index! - startKpt.ui!.frame_index!);
      const x = vertex.x + xInterpolation * (imageIndex - startKpt.ui!.frame_index!);
      const y = vertex.y + yInterpolation * (imageIndex - startKpt.ui!.frame_index!);
      return { ...vertex, x, y };
    });
    // make a new KeypointsTemplate with interpolated coords
    const interpolatedKpt = structuredClone(startKpt);
    interpolatedKpt.id = nanoid(5); //not needed but it still ensure unique id
    interpolatedKpt.ui!.frame_index = imageIndex;
    interpolatedKpt.ui!.displayControl = {
      hidden: startKpt.ui!.displayControl?.hidden,
      editing: false,
    };
    //if editing, we highlight only current frame object, else we keep hihlighted status of startRef
    interpolatedKpt.ui!.highlighted = startKpt.ui!.displayControl?.editing
      ? "none"
      : startKpt.ui!.highlighted;
    interpolatedKpt.viewRef = { id: view_id, name: startKpt.viewRef?.name || "" }; //for lint
    // for convenience, we store ref to start kpts
    interpolatedKpt.ui!.startRef = startKpt;
    // top_entities (if exist) lost class with structuredClone: replace it
    interpolatedKpt.ui!.top_entities = startKpt.ui!.top_entities;
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
  rightTracklet.ui.top_entities = tracklet2split.ui.top_entities;
  //tracklet2split become left tracklet
  tracklet2split.data.end_timestep = prev;
  tracklet2split.ui.childs = tracklet2split.ui.childs.filter((ann) => ann.ui.frame_index! <= prev);

  const pixSource = getPixanoSource(sourcesStore);
  tracklet2split.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
  const save_item_left: SaveItem = {
    change_type: "update",
    object: tracklet2split,
  };
  saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_left));
  rightTracklet.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
  const save_item_right: SaveItem = {
    change_type: "add",
    object: rightTracklet,
  };
  saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_right));
  return rightTracklet;
};

export const sortByFrameIndex = (a: Annotation, b: Annotation) => {
  if (a.is_type(BaseSchema.Tracklet) && b.is_type(BaseSchema.Tracklet)) {
    return (a as Tracklet).data.start_timestep - (b as Tracklet).data.start_timestep;
  } else {
    const indexA = a.ui.frame_index !== undefined ? a.ui.frame_index : Number.POSITIVE_INFINITY;
    const indexB = b.ui.frame_index !== undefined ? b.ui.frame_index : Number.POSITIVE_INFINITY;
    return indexA - indexB;
  }
};

export const setBufferSpecs = () => {
  const n_view = Object.keys(get(imagesPerViewBuffer)).length;
  previousCount = Math.round((ratioOfBackwardBuffer * bufferSize) / n_view);
  nextCount = Math.round(((1 - ratioOfBackwardBuffer) * bufferSize) / n_view);
  //reset imagesPerView store
  imagesPerView.set({});
};

function preloadViewsImage(index: number) {
  Object.entries(get(imagesFilesUrlsByFrame)[index]).map(([viewKey, im_ref]) => {
    if (im_ref && !get(imagesPerViewBuffer)[viewKey][index]) {
      void new Promise<void>((resolve, reject) => {
        const img = new Image();
        img.src = `/${im_ref.url}`;
        img.onload = () => {
          imagesPerViewBuffer.update((buff) => {
            buff[viewKey][index] = {
              id: im_ref.id,
              element: img,
            };
            return buff;
          });
          resolve();
        };
        img.onerror = () => {
          console.warn(`Failed to load image: ${im_ref.url}`);
          reject(new Error(`Failed to load image: ${im_ref.url}`));
        };
      });
    }
  });
}

function preloadImagesProgressively(currentIndex: number = 0) {
  const previous: number[] = [];
  const next: number[] = [];

  const num_frames = get(lastFrameIndex) + 1;
  if (num_frames > 1) {
    // previous (inverted and circular)
    for (let i = 1; i <= previousCount; i++) {
      previous.push((currentIndex - i + num_frames) % num_frames);
    }
    // next (inculing current, circular)
    for (let i = 0; i < nextCount; i++) {
      next.push((currentIndex + i) % num_frames);
    }
  }
  const includedIndices = new Set([...previous, ...next]);
  const excludedIndices = Array.from({ length: num_frames }, (_, i) => i).filter(
    (index) => !includedIndices.has(index),
  );

  clearTimeout(timerId); // reinit timer on each update
  timerId = setTimeout(() => {
    for (const i of next) {
      preloadViewsImage(i);
    }
    for (const i of previous) {
      preloadViewsImage(i);
    }
  }, 20); // timeout to spare bandwith (cancel outdated updates)

  //delete buffered images out of currentIndex window (currentIndex -10 : currentIndex + 30)
  imagesPerViewBuffer.update((buff) => {
    Object.keys(buff).forEach((viewKey) => {
      for (const i of excludedIndices) {
        if (i in buff[viewKey]) {
          delete buff[viewKey][i]; // eslint-disable-line @typescript-eslint/no-array-delete
        }
      }
    });
    return buff;
  });
}

export const updateView = (imageIndex: number) => {
  if (get(imagesFilesUrlsByFrame).length === 0) return;
  preloadImagesProgressively(imageIndex);
  const buffer = get(imagesPerViewBuffer);
  Object.entries(get(imagesFilesUrlsByFrame)[imageIndex]).forEach(([key, im_ref]) => {
    if (key in buffer && buffer[key][imageIndex] && buffer[key][imageIndex].element.complete) {
      imagesPerView.update((ipv) => {
        ipv[key] = [...(ipv[key] || []), buffer[key][imageIndex]].slice(-2);
        return ipv;
      });
    } else {
      if (im_ref) {
        const image = new Image();
        const src = `/${im_ref.url}`;
        if (!src) return;
        image.src = src;
        //NOTE double image, avoid flashing by "swapping" with previous image
        imagesPerView.update((ipv) => {
          ipv[key] = [...(ipv[key] || []), { id: im_ref.id, element: image }].slice(-2);
          return ipv;
        });
      } else {
        //console.warn("Media not present")
      }
    }
  });
};
