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
import type {
  Shape,
  InteractiveImageSegmenter,
  ItemObject,
  DatasetItem,
  Mask,
  BBox,
  ItemFeature,
  FeaturesValues,
} from "@pixano/core";

import { mapObjectToBBox, mapObjectToMasks } from "../api/objectsApi";
import type { ModelSelection } from "../types/datasetItemWorkspaceTypes";

// Exports
export const newShape = writable<Shape>();
export const itemObjects = writable<ItemObject[]>([]);
export const interactiveSegmenterModel = writable<InteractiveImageSegmenter>();
export const itemMetas = writable<{
  sceneFeatures: DatasetItem["features"]; // features
  objectFeatures: Record<string, ItemFeature>; // itemFeatures
  featuresList: FeaturesValues; // featuresValues
  views: DatasetItem["views"];
  id: DatasetItem["id"];
}>();
export const canSave = writable<boolean>(false);
export const preAnnotationIsActive = writable<boolean>(false);
export const modelsStore = writable<ModelSelection>({
  currentModalOpen: "none",
  selectedModelName: "",
});

export const itemBboxes = derived([itemObjects, itemMetas], ([$itemObjects, $itemMetas]) =>
  $itemObjects.reduce((acc, object) => {
    const box = mapObjectToBBox(object, $itemMetas?.views);
    acc = [...acc, ...(box ? [box] : [])];
    return acc;
  }, [] as BBox[]),
);

export const itemMasks = derived(itemObjects, ($itemObjects) =>
  $itemObjects.reduce((acc, object) => {
    const mask = mapObjectToMasks(object);
    acc = [...acc, ...(mask ? [mask] : [])];
    return acc;
  }, [] as Mask[]),
);
