/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { entitiesById, mediaViews, tracks } from "./annotationDerivedStores.svelte";
import {
  collectFrameAnnotations,
  collectExactFrameAnnotations,
  getAnnotationFrameIndex,
  getBBoxInterpolationIdentity,
  getKeypointsInterpolationIdentity,
} from "./frameAnnotationSelectors";
import { reactiveDerived } from "./reactiveStore.svelte";
import { currentFrameIndex } from "./videoStores.svelte";
import {
  annotations,
  highlightedEntity,
  interpolate,
  selectedTool,
} from "./workspaceBaseStores.svelte";
import { NOT_ANNOTATION_ITEM_OPACITY } from "$lib/constants/workspaceConstants";
import { ToolType } from "$lib/tools";
import {
  BaseSchema,
  BBox,
  Keypoints,
  Mask,
  MultiPath,
} from "$lib/types/dataset";
import type { KeypointAnnotation } from "$lib/types/shapeTypes";
import {
  mapBBoxForDisplay,
  mapKeypointsForDisplay,
  mapMaskForDisplay,
} from "$lib/utils/annotationMapping";
import { getEffectiveHighlight } from "$lib/utils/highlightUtils";
import { boxLinearInterpolation, keypointsLinearInterpolation } from "$lib/utils/interpolation";

// --- Frame bucketing ---

function pushFrameEntry<T>(
  byFrame: Map<number, T[]>,
  frameIndex: number | undefined,
  value: T,
): void {
  if (frameIndex === undefined) return;
  const bucket = byFrame.get(frameIndex);
  if (bucket) {
    bucket.push(value);
    return;
  }
  byFrame.set(frameIndex, [value]);
}

type FrameBuckets = {
  bboxes: Map<number, BBox[]>;
  keypoints: Map<number, Keypoints[]>;
  masks: Map<number, Mask[]>;
  multiPaths: Map<number, MultiPath[]>;
};

const _frameBuckets = $derived.by<FrameBuckets>(() => {
  const bboxes = new Map<number, BBox[]>();
  const keypoints = new Map<number, Keypoints[]>();
  const masks = new Map<number, Mask[]>();
  const multiPaths = new Map<number, MultiPath[]>();

  for (const ann of annotations.value) {
    const frameIndex = getAnnotationFrameIndex(ann);
    if (ann.is_type(BaseSchema.BBox)) {
      pushFrameEntry(bboxes, frameIndex, ann as BBox);
      continue;
    }
    if (ann.is_type(BaseSchema.Keypoints)) {
      pushFrameEntry(keypoints, frameIndex, ann as Keypoints);
      continue;
    }
    if (ann.is_type(BaseSchema.Mask)) {
      pushFrameEntry(masks, frameIndex, ann as Mask);
      continue;
    }
    if (ann.is_type(BaseSchema.MultiPath)) {
      pushFrameEntry(multiPaths, frameIndex, ann as MultiPath);
    }
  }

  return { bboxes, keypoints, masks, multiPaths };
});
// --- Current-frame derived stores ---

export const current_itemBBoxes = reactiveDerived(() => {
  const frameIdx = currentFrameIndex.value;
  const mViews = mediaViews.value;
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const eById = entitiesById.value;

  const { results } = collectFrameAnnotations<BBox, BBox>({
    frameAnnotations: _frameBuckets.bboxes.get(frameIdx) ?? [],
    typeFilter: (ann): ann is BBox => ann.is_type(BaseSchema.BBox),
    mapForDisplay: (bbox, hl) => mapBBoxForDisplay(bbox, mViews, hl),
    interpolateFn: boxLinearInterpolation,
    interpolationIdentity: getBBoxInterpolationIdentity,
    frameIdx,
    doInterpolate: interpolate.value,
    tracks: tracks.value,
    mViews,
    focusedEntityId,
    selectedToolType,
    entitiesById: eById,
  });

  return results;
});

export const current_itemKeypoints = reactiveDerived(() => {
  const frameIdx = currentFrameIndex.value;
  const mViews = mediaViews.value;

  const { results } = collectFrameAnnotations<Keypoints, KeypointAnnotation>({
    frameAnnotations: _frameBuckets.keypoints.get(frameIdx) ?? [],
    typeFilter: (ann): ann is Keypoints => ann.is_type(BaseSchema.Keypoints),
    mapForDisplay: (kpt, hl) => mapKeypointsForDisplay(kpt, mViews, hl),
    interpolateFn: keypointsLinearInterpolation,
    interpolationIdentity: getKeypointsInterpolationIdentity,
    frameIdx,
    doInterpolate: interpolate.value,
    tracks: tracks.value,
    mViews,
    focusedEntityId: highlightedEntity.value,
    selectedToolType: selectedTool.value?.type ?? ToolType.Pan,
    entitiesById: entitiesById.value,
  });

  return results;
});

export const current_itemMasks = reactiveDerived(() => {
  const frameIdx = currentFrameIndex.value;
  const frameMasks = _frameBuckets.masks.get(frameIdx) ?? [];
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const eById = entitiesById.value;

  return collectExactFrameAnnotations<Mask, Mask>({
    frameAnnotations: frameMasks,
    mapForDisplay: mapMaskForDisplay,
    focusedEntityId,
    selectedToolType,
    entitiesById: eById,
  });
});

export const current_itemMultiPaths = reactiveDerived(() => {
  const frameIdx = currentFrameIndex.value;
  const frameMultiPaths = _frameBuckets.multiPaths.get(frameIdx) ?? [];
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const eById = entitiesById.value;

  const currentMultiPaths: MultiPath[] = [];
  for (const mp of frameMultiPaths) {
    const effectiveHighlight = getEffectiveHighlight(mp, focusedEntityId, selectedToolType, eById);
    currentMultiPaths.push({
      ...mp,
      ui: {
        ...mp.ui,
        displayControl: { ...mp.ui.displayControl, highlighted: effectiveHighlight },
        opacity: effectiveHighlight === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
      },
    } as unknown as MultiPath);
  }

  return currentMultiPaths;
});
