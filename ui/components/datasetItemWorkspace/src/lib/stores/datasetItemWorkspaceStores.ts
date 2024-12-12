/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import {
  type InteractiveImageSegmenter,
  type KeypointsTemplate,
  type SaveItem,
  type SelectionTool,
  type Shape,
  Annotation,
  BaseSchema,
  BBox,
  Entity,
  Keypoints,
  Mask,
  TextSpan,
  Tracklet,
  utils,
  View,
} from "@pixano/core";
import { derived, writable } from "svelte/store";

import { mapObjectToBBox, mapObjectToKeypoints, mapObjectToMasks } from "../api/objectsApi";
import type { Filters, ItemsMeta, ModelSelection } from "../types/datasetItemWorkspaceTypes";

// Exports
export const newShape = writable<Shape>();
export const selectedTool = writable<SelectionTool>();
export const annotations = writable<Annotation[]>([]);
export const entities = writable<Entity[]>([]);
export const views = writable<Record<string, View | View[]>>({});
export const interactiveSegmenterModel = writable<InteractiveImageSegmenter>();
export const itemMetas = writable<ItemsMeta>();
export const preAnnotationIsActive = writable<boolean>(false);
export const modelsUiStore = writable<ModelSelection>({
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
export const selectedKeypointsTemplate = writable<KeypointsTemplate["template_id"] | null>(null);

export const saveData = writable<SaveItem[]>([]);
export const canSave = derived(saveData, ($saveData) => $saveData.length > 0);
type ColorScale = [Array<string>, (id: string) => string];

const initialColorScale: ColorScale = [[], utils.ordinalColorScale([])];

export const colorScale = derived(
  entities,
  ($entities, _, update) => {
    update((old) => {
      let allIds = $entities.map((obj) => obj.id);
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
  [annotations, views, entities],
  ([$annotations, $views, $entities]) => {
    const bboxes: BBox[] = [];
    for (const ann of $annotations) {
      if (ann.is_type(BaseSchema.BBox)) {
        const box = mapObjectToBBox(ann as BBox, $views, $entities);
        if (box) bboxes.push(box);
      }
    }
    return bboxes;
  },
);

export const itemMasks = derived(annotations, ($annotations) => {
  const masks: Mask[] = [];
  for (const ann of $annotations) {
    if (ann.is_type(BaseSchema.Mask)) {
      const mask = mapObjectToMasks(ann as Mask);
      if (mask) masks.push(mask);
    }
  }
  return masks;
});

export const itemKeypoints = derived([annotations, views], ([$annotations, $views]) => {
  const m_keypoints: KeypointsTemplate[] = [];
  for (const ann of $annotations) {
    if (ann.is_type(BaseSchema.Keypoints)) {
      const kpt = mapObjectToKeypoints(ann as Keypoints, $views);
      if (kpt) m_keypoints.push(kpt);
    }
  }
  return m_keypoints;
});

export const tracklets = derived(annotations, ($annotations) => {
  return $annotations.filter((annotation) => annotation.is_type(BaseSchema.Tracklet)) as Tracklet[];
});

export const textSpans = derived(annotations, ($annotations) => {
  return $annotations.filter((annotation) => annotation.is_type(BaseSchema.TextSpan)) as TextSpan[];
});
