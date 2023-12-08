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
  ObjectContent,
  InteractiveImageSegmenter,
  ItemObject,
  Mask,
  BBox,
} from "@pixano/core";

import { allObjects } from "../mock";
import { mapObjectToBBox, mapObjectToMasks } from "../api/objectsApi";
import { GROUND_TRUTH, MODEL_RUN } from "../constants";

// Exports
export const newShape = writable<Shape | null>();
export const objects = writable<ObjectContent[]>([]);
export const itemObjects = writable<ItemObject[]>([]);
export const interactiveSegmenterModel = writable<InteractiveImageSegmenter>();
export const colorRange = writable<string[]>(["0", "10"]);

export const itemBboxes = derived(itemObjects, ($itemObjects) =>
  $itemObjects.reduce((acc, object) => {
    if (object.source_id === GROUND_TRUTH || object.source_id === MODEL_RUN) {
      acc = [...acc, mapObjectToBBox(object)];
    }
    return acc;
  }, [] as BBox[]),
);

export const itemMasks = derived(itemObjects, ($itemObjects) =>
  $itemObjects.reduce((acc, object) => {
    if (object.source_id === GROUND_TRUTH || object.source_id === MODEL_RUN) {
      const mask = mapObjectToMasks(object);
      acc = [...acc, ...(mask ? [mask] : [])];
    }
    return acc;
  }, [] as Mask[]),
);

// add mock objects
objects.set(allObjects);
