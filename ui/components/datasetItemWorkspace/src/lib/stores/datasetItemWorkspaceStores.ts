/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import { derived, writable } from "svelte/store";

import {
  Annotation,
  BaseSchema,
  BBox,
  Entity,
  isMediaView,
  isTextView,
  Keypoints,
  Mask,
  Message,
  TextSpan,
  Tracklet,
  utils,
  View,
  type InteractiveImageSegmenter,
  type KeypointsTemplate,
  type SaveItem,
  type SelectionTool,
  type Shape,
} from "@pixano/core";

import {
  mapObjectToBBox,
  mapObjectToKeypoints,
  mapObjectToMasks,
  type MView,
} from "../api/objectsApi";
import type {
  Filters,
  ItemsMeta,
  Merges,
  ModelSelection,
} from "../types/datasetItemWorkspaceTypes";

// Exports
export const newShape = writable<Shape>();
export const selectedTool = writable<SelectionTool>();
export const annotations = writable<Annotation[]>([]);
export const entities = writable<Entity[]>([]);
export const views = writable<Record<string, View | View[]>>({});
export const merges = writable<Merges>({ to_fuse: [], forbids: [] });
export const interactiveSegmenterModel = writable<InteractiveImageSegmenter>();
export const itemMetas = writable<ItemsMeta>();
export const preAnnotationIsActive = writable<boolean>(false);
export const modelsUiStore = writable<ModelSelection>({
  currentModalOpen: "none",
  selectedModelName: "",
  selectedTableName: "",
  yetToLoadEmbedding: true,
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
const resetColorScaleTrigger = writable(0);
export const colorScale = derived(
  [entities, resetColorScaleTrigger],
  ([$entities, $resetColorScale], _, update) => {
    update((old) => {
      if ($resetColorScale > 0) {
        resetColorScaleTrigger.set(0);
        return initialColorScale;
      }
      let allIds = $entities.filter((ent) => ent.data.parent_ref.id === "").map((obj) => obj.id);
      if (old) {
        allIds = [...old[0], ...allIds];
        allIds = [...new Set(allIds)];
      }
      return [allIds, utils.ordinalColorScale(allIds)] as ColorScale;
    });
  },
  initialColorScale,
);
export function resetColorScale() {
  resetColorScaleTrigger.set(1);
}

export const mediaViews = derived(views, ($views) => {
  // Do not use Object.entries().filter because it loses the type information
  const mediaViews: MView = {};
  for (const [key, view] of Object.entries($views)) {
    if (isMediaView(view)) {
      mediaViews[key] = view;
    }
  }
  return mediaViews;
});

export const textViews = derived(views, ($views) =>
  Object.values($views).filter((view) => isTextView(view)),
);

export const itemBboxes = derived([annotations, mediaViews], ([$annotations, $mediaViews]) => {
  const bboxes: BBox[] = [];
  for (const ann of $annotations) {
    if (ann.is_type(BaseSchema.BBox)) {
      const box = mapObjectToBBox(ann as BBox, $mediaViews);
      if (box) bboxes.push(box);
    }
  }
  return bboxes;
});

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

export const itemKeypoints = derived([annotations, mediaViews], ([$annotations, $views]) => {
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

export const messages = derived(annotations, ($annotations) => {
  return $annotations.filter((annotation) => annotation.is_type(BaseSchema.Message)) as Message[];
});

export const conversations = derived(entities, ($entities) => {
  return $entities.filter((entities) => entities.is_type(BaseSchema.Conversation));
});
