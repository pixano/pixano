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
  type DatasetItem,
  type Mask,
  type BBox,
  type ItemFeature,
  type FeaturesValues,
  type SelectionTool,
  utils,
} from "@pixano/core";

import { mapObjectToBBox, mapObjectToMasks } from "../api/objectsApi";
import type { ModelSelection } from "../types/datasetItemWorkspaceTypes";

// Exports
export const newShape = writable<Shape>();
export const selectedTool = writable<SelectionTool>();
export const itemObjects = writable<ItemObject[]>([]);
export const interactiveSegmenterModel = writable<InteractiveImageSegmenter>();
export const itemMetas = writable<{
  mainFeatures: DatasetItem["features"]; // features
  objectFeatures: Record<string, ItemFeature>; // itemFeatures
  featuresList: FeaturesValues; // featuresValues
  views: DatasetItem["views"];
  id: DatasetItem["id"];
  type: DatasetItem["type"];
}>();
export const canSave = writable<boolean>(false);
export const preAnnotationIsActive = writable<boolean>(false);
export const modelsStore = writable<ModelSelection>({
  currentModalOpen: "none",
  selectedModelName: "",
});

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
