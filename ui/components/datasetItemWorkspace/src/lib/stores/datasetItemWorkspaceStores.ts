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
  type Mask,
  type BBox,
  type SelectionTool,
  utils,
  type KeypointsTemplate,
  type SaveItem,
  Annotation,
  Entity,
} from "@pixano/core";

import { mapObjectToBBox, mapObjectToKeypoints, mapObjectToMasks } from "../api/objectsApi";
import type { Filters, ItemsMeta, ModelSelection } from "../types/datasetItemWorkspaceTypes";

// Exports
export const newShape = writable<Shape>();
export const selectedTool = writable<SelectionTool>();
export const annotations = writable<Annotation[]>([]);
export const entities = writable<Entity[]>([]);
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

export const saveData = writable<SaveItem[]>([]);

type ColorScale = [Array<string>, (id: string) => string];

const initialColorScale: ColorScale = [[], utils.ordinalColorScale([])];

export const colorScale = derived(
  annotations,
  ($annotations, _, update) => {
    update((old) => {
      let allIds = $annotations.map((obj) => obj.id);
      if (old) {
        allIds = [...old[0], ...allIds];
        allIds = [...new Set(allIds)];
      }
      return [allIds, utils.ordinalColorScale(allIds)] as ColorScale;
    });
  },
  initialColorScale,
);

export const itemBboxes = derived(
  [annotations, itemMetas, entities],
  ([$annotations, $itemMetas, $entities]) => {
    const bboxes: BBox[] = [];
    for (const ann of $annotations) {
      if (ann.is_bbox) {
        //maybe we should not cycle on this, but mapObjectToBBox return BBox[] for now...
        const item_boxes = mapObjectToBBox(ann, $itemMetas?.views, $entities);
        for (const box of item_boxes) bboxes.push(box);
      }
    }
    return bboxes;
  },
);

export const itemMasks = derived(annotations, ($annotations) => {
  const masks: Mask[] = [];
  for (const ann of $annotations) {
    if (ann.is_mask) {
      masks.push(mapObjectToMasks(ann));
    }
  }
  return masks;
});

export const itemKeypoints = derived([annotations, itemMetas], ([$annotations, $itemMetas]) => {
  const m_keypoints: KeypointsTemplate[] = [];
  for (const ann of $annotations) {
    if (ann.is_keypoints) {
      const item_keypoints = mapObjectToKeypoints(object, $itemMetas?.views);
      for (const keypoints of item_keypoints) m_keypoints.push(keypoints);
    }
  }
  return m_keypoints;
});
