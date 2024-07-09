/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

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
export const imageSmoothing = writable<boolean>(true);
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
    const boxes = mapObjectToBBox(object, $itemMetas?.views);
    for (const box of boxes) {
      if (box) acc.push(box);
    }
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
    const m_keypoints = mapObjectToKeypoints(object, $itemMetas?.views);
    for (const keypoints of m_keypoints) {
      if (keypoints) acc.push(keypoints);
    }
    return acc;
  }, [] as KeypointsTemplate[]);
});
