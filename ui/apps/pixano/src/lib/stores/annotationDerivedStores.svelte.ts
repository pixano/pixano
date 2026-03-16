/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { reactiveDerived } from "./reactiveStore.svelte";
import {
  annotations,
  entities,
  generatedPreviewBBoxes,
  highlightedEntity,
  selectedTool,
  views,
} from "./workspaceBaseStores.svelte";
import { ToolType } from "$lib/tools";
import {
  BaseSchema,
  BBox,
  isMediaView,
  isTextView,
  Keypoints,
  Mask,
  Message,
  TextSpan,
  Tracklet,
  type View,
} from "$lib/types/dataset";
import type { KeypointAnnotation } from "$lib/types/shapeTypes";
import type { MView } from "$lib/types/workspace";
import {
  mapBBoxForDisplay,
  mapKeypointsForDisplay,
  mapMaskForDisplay,
} from "$lib/utils/annotationMapping";
import { getEffectiveHighlight } from "$lib/utils/highlightUtils";

// --- Shared entity-by-id map ---
// Only built when Pan tool + focused entity (used by highlight logic).

export const entitiesById = reactiveDerived(() => {
  const focusedEntityId = highlightedEntity.value;
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  if (selectedToolType !== ToolType.Pan || !focusedEntityId) return null;
  return new Map(entities.value.map((entity) => [entity.id, entity]));
});

// --- Media / text views ---

export const mediaViews = reactiveDerived<MView>(() => {
  const mediaViewsResult: MView = {};
  for (const [key, view] of Object.entries(views.value)) {
    if (isMediaView(view)) {
      mediaViewsResult[key] = view;
    }
  }
  return mediaViewsResult;
});

export const textViews = reactiveDerived(() =>
  Object.values(views.value).filter((view: View | View[]) => isTextView(view)),
);

// --- Annotation-type derived stores ---

export const itemBboxes = reactiveDerived(() => {
  const bboxes: BBox[] = [];
  const mViews = mediaViews.value;
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const eById = entitiesById.value;

  for (const ann of annotations.value) {
    if (ann.is_type(BaseSchema.BBox)) {
      const bbox = ann as BBox;
      const box = mapBBoxForDisplay(
        bbox,
        mViews,
        getEffectiveHighlight(bbox, focusedEntityId, selectedToolType, eById),
      );
      if (box) bboxes.push(box);
    }
  }
  for (const previewBBox of generatedPreviewBBoxes.value) {
    const box = mapBBoxForDisplay(
      previewBBox,
      mViews,
      getEffectiveHighlight(previewBBox, focusedEntityId, selectedToolType, eById),
    );
    if (box) bboxes.push(box);
  }
  return bboxes;
});

export const itemMasks = reactiveDerived(() => {
  const masks: Mask[] = [];
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const eById = entitiesById.value;

  for (const ann of annotations.value) {
    if (ann.is_type(BaseSchema.Mask)) {
      const rawMask = ann as Mask;
      const mask = mapMaskForDisplay(
        rawMask,
        getEffectiveHighlight(rawMask, focusedEntityId, selectedToolType, eById),
      );
      if (mask) masks.push(mask);
    }
  }
  return masks;
});

export const itemKeypoints = reactiveDerived(() => {
  const mViews = mediaViews.value;
  const m_keypoints: KeypointAnnotation[] = [];
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const eById = entitiesById.value;

  for (const ann of annotations.value) {
    if (ann.is_type(BaseSchema.Keypoints)) {
      const keypoint = ann as Keypoints;
      const kpt = mapKeypointsForDisplay(
        keypoint,
        mViews,
        getEffectiveHighlight(keypoint, focusedEntityId, selectedToolType, eById),
      );
      if (kpt) m_keypoints.push(kpt);
    }
  }
  return m_keypoints;
});

export const tracks = reactiveDerived(
  () =>
    annotations.value.filter((annotation) => annotation.is_type(BaseSchema.Tracklet)) as Tracklet[],
);

export const textSpans = reactiveDerived(() => {
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const eById = entitiesById.value;

  const spans = annotations.value.filter((annotation) =>
    annotation.is_type(BaseSchema.TextSpan),
  ) as TextSpan[];

  return spans.map((span) => {
    const effectiveHighlight = getEffectiveHighlight(
      span,
      focusedEntityId,
      selectedToolType,
      eById,
    );
    if (effectiveHighlight === span.ui.displayControl.highlighted) return span;
    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
    const clone = Object.assign(Object.create(Object.getPrototypeOf(span)), span);
    clone.ui = {
      ...span.ui,
      displayControl: { ...span.ui.displayControl, highlighted: effectiveHighlight },
    };
    return clone as TextSpan;
  });
});

export const messages = reactiveDerived(
  () =>
    annotations.value.filter((annotation) => annotation.is_type(BaseSchema.Message)) as Message[],
);
