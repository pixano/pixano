/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import * as ort from "onnxruntime-web";
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
  SequenceFrame,
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
import { boxLinearInterpolation, keypointsLinearInterpolation } from "../api/videoApi";
import type {
  Filters,
  ItemsMeta,
  Merges,
  ModelSelection,
} from "../types/datasetItemWorkspaceTypes";
import { currentFrameIndex } from "./videoViewerStores";

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
export const embeddings = writable<Record<string, ort.Tensor>>({});

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

export const current_itemBBoxes = derived(
  [itemBboxes, currentFrameIndex, tracklets, mediaViews],
  ([$itemBboxes, $currentFrameIndex, $tracklets, $mediaViews]) => {
    const current_bboxes_and_interpolated: BBox[] = [];
    const current_tracklets = $tracklets.filter(
      (tracklet) =>
        tracklet.data.start_timestep <= $currentFrameIndex &&
        tracklet.data.end_timestep >= $currentFrameIndex,
    );
    for (const tracklet of current_tracklets) {
      const bbox_childs_ids = new Set(
        tracklet.ui.childs?.filter((ann) => ann.is_type(BaseSchema.BBox)).map((bbox) => bbox.id),
      );
      const bbox_childs = $itemBboxes.filter((bbox) => bbox_childs_ids.has(bbox.id));
      const box = bbox_childs.find((box) => box.ui.frame_index === $currentFrameIndex);
      if (box) current_bboxes_and_interpolated.push(box);
      else if (bbox_childs.length > 1) {
        const sample_bbox = bbox_childs[0];
        const view_id = ($mediaViews[sample_bbox.data.view_ref.name] as SequenceFrame[])[
          $currentFrameIndex
        ].id;
        const interpolated_box = boxLinearInterpolation(bbox_childs, $currentFrameIndex, view_id);
        if (interpolated_box) current_bboxes_and_interpolated.push(interpolated_box);
      }
    }
    return current_bboxes_and_interpolated;
  },
);

export const current_itemKeypoints = derived(
  [itemKeypoints, currentFrameIndex, tracklets, mediaViews],
  ([$itemKeypoints, $currentFrameIndex, $tracklets, $mediaViews]) => {
    const current_kpts_and_interpolated: KeypointsTemplate[] = [];
    const current_tracklets = $tracklets.filter(
      (tracklet) =>
        tracklet.data.start_timestep <= $currentFrameIndex &&
        tracklet.data.end_timestep >= $currentFrameIndex,
    );
    for (const tracklet of current_tracklets) {
      const kpt_childs_ids = new Set(
        tracklet.ui.childs?.filter((ann) => ann.is_type(BaseSchema.Keypoints)).map((kpt) => kpt.id),
      );
      const kpt_childs = $itemKeypoints.filter((kpt) => kpt_childs_ids.has(kpt.id));
      const kpt = kpt_childs.find((kpt) => kpt.ui!.frame_index === $currentFrameIndex);
      if (kpt) current_kpts_and_interpolated.push(kpt);
      else if (kpt_childs.length > 1) {
        const sample_kpt = kpt_childs[0];
        const view_id = ($mediaViews[sample_kpt.viewRef!.name] as SequenceFrame[])[
          $currentFrameIndex
        ].id;
        const interpolated_kpt = keypointsLinearInterpolation(
          kpt_childs,
          $currentFrameIndex,
          view_id,
        );
        if (interpolated_kpt) current_kpts_and_interpolated.push(interpolated_kpt);
      }
    }
    return current_kpts_and_interpolated;
  },
);

export const current_itemMasks = derived(
  [itemMasks, currentFrameIndex, tracklets],
  ([$itemMasks, $currentFrameIndex, $tracklets]) => {
    const current_masks: Mask[] = [];
    const current_tracklets = $tracklets.filter(
      (tracklet) =>
        tracklet.data.start_timestep <= $currentFrameIndex &&
        tracklet.data.end_timestep >= $currentFrameIndex,
    );
    for (const tracklet of current_tracklets) {
      const mask_childs_ids = new Set(
        tracklet.ui.childs?.filter((ann) => ann.is_type(BaseSchema.Mask)).map((mask) => mask.id),
      );
      const mask_childs = $itemMasks.filter((mask) => mask_childs_ids.has(mask.id));
      const mask = mask_childs.find((mask) => mask.ui.frame_index === $currentFrameIndex);
      if (mask) current_masks.push(mask);
    }
    return current_masks;
  },
);
