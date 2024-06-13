/**
 * @copyright CEA
 * @author CEA
 * @license CECILL
 *
 * This software is a collaborative computer program whose purpose is to
 * generate and explore labeled data for computer vision applications.
 * This software is governed by the CeCILL-C license under French law and
 * abiding by the rules of distribution of free software. You can use,
 * modify and/ or redistribute the software under the terms of the CeCILL-C
 * license as circulated by CEA, CNRS and INRIA at the following URL
 *
 * http://www.cecill.info
 */

// Imports
import { writable, derived } from "svelte/store";
import {
  type Shape,
  type InteractiveImageSegmenter,
  type ItemObject,
  type Mask,
  type BBox,
  type SelectionTool,
  utils,
  type KeypointsTemplate,
} from "@pixano/core";

import { mapObjectToBBox, mapObjectToKeypoints, mapObjectToMasks } from "../api/objectsApi";
import type { Filters, ItemsMeta, ModelSelection } from "../types/datasetItemWorkspaceTypes";

// Exports
export const newShape = writable<Shape>();
export const selectedTool = writable<SelectionTool>();
export const itemObjects = writable<ItemObject[]>([]);
export const interactiveSegmenterModel = writable<InteractiveImageSegmenter>();
export const itemMetas = writable<ItemsMeta>();
export const canSave = writable<boolean>(false);
export const preAnnotationIsActive = writable<boolean>(false);
export const modelsStore = writable<ModelSelection>({
  currentModalOpen: "none",
  selectedModelName: "",
});
export const filters = writable<Filters>({
  brightness: 0,
  contrast: 0,
  equalizeHistogram: false,
  redRange: [0, 255],
  greenRange: [0, 255],
  blueRange: [0, 255],
  u16BitRange: [0, 65535],
});
export const selectedKeypointsTemplate = writable<KeypointsTemplate["id"] | null>(null);

type ColorScale = [Array<string>, (id: string) => string];

const initialColorScale: ColorScale = [[], utils.ordinalColorScale([])];

export const colorScale = derived(
  itemObjects,
  ($itemObjects, _, update) => {
    update((old) => {
      let allIds = $itemObjects.map((obj) => obj.id);
      if (old) {
        allIds = [...old[0], ...allIds];
        allIds = [...new Set(allIds)];
      }
      return [allIds, utils.ordinalColorScale(allIds)] as ColorScale;
    });
  },
  initialColorScale,
);

export const itemBboxes = derived([itemObjects, itemMetas], ([$itemObjects, $itemMetas]) =>
  $itemObjects.reduce((acc, object) => {
    const box = mapObjectToBBox(object, $itemMetas?.views);
    if (box) acc.push(box);
    return acc;
  }, [] as BBox[]),
);

export const itemMasks = derived(itemObjects, ($itemObjects) =>
  $itemObjects.reduce((acc, object) => {
    const mask = mapObjectToMasks(object);
    if (mask) acc.push(mask);
    return acc;
  }, [] as Mask[]),
);

export const itemKeypoints = derived([itemObjects, itemMetas], ([$itemObjects, $itemMetas]) => {
  return $itemObjects.reduce((acc, object) => {
    const keypoints = mapObjectToKeypoints(object, $itemMetas?.views);
    if (keypoints) acc.push(keypoints);
    return acc;
  }, [] as KeypointsTemplate[]);
});
