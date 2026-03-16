/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { entitiesById, mediaViews, tracks } from "./annotationDerivedStores.svelte";
import { reactiveDerived } from "./reactiveStore.svelte";
import { currentFrameIndex } from "./videoStores.svelte";
import {
  annotations,
  generatedPreviewBBoxes,
  highlightedEntity,
  interpolate,
  selectedTool,
} from "./workspaceBaseStores.svelte";
import { NOT_ANNOTATION_ITEM_OPACITY } from "$lib/constants/workspaceConstants";
import { ToolType } from "$lib/tools";
import {
  Annotation,
  BaseSchema,
  BBox,
  Entity,
  Keypoints,
  Mask,
  MultiPath,
  SequenceFrame,
  Tracklet,
} from "$lib/types/dataset";
import type { KeypointAnnotation } from "$lib/types/shapeTypes";
import type { MView } from "$lib/types/workspace";
import {
  mapBBoxForDisplay,
  mapKeypointsForDisplay,
  mapMaskForDisplay,
} from "$lib/utils/annotationMapping";
import { getEffectiveHighlight, type HighlightState } from "$lib/utils/highlightUtils";
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
    const frameIndex = ann.ui.frame_index;
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

// --- Generic frame interpolation helper ---

function collectFrameAnnotations<TRaw extends Annotation, TDisplay extends { id: string }>(opts: {
  frameAnnotations: TRaw[];
  typeFilter: (ann: Annotation) => ann is TRaw;
  mapForDisplay: (ann: TRaw, highlight: HighlightState) => TDisplay | undefined;
  interpolateFn: (mapped: TDisplay[], frameIdx: number, frameId: string) => TDisplay | null;
  frameIdx: number;
  doInterpolate: boolean;
  tracks: Tracklet[];
  mViews: MView;
  focusedEntityId: string | null;
  selectedToolType: ToolType;
  entitiesById: Map<string, Entity> | null;
}): { results: TDisplay[]; seenIds: Set<string> } {
  const results: TDisplay[] = [];
  const seenIds = new Set<string>();

  if (opts.doInterpolate) {
    const currentTracklets = opts.tracks.filter(
      (t) => t.data.start_frame <= opts.frameIdx && t.data.end_frame >= opts.frameIdx,
    );

    for (const tracklet of currentTracklets) {
      const childs = (tracklet.ui.childs ?? []).filter(opts.typeFilter);

      const atFrame = childs.find((ann) => ann.ui.frame_index === opts.frameIdx);
      if (atFrame) {
        const mapped = opts.mapForDisplay(
          atFrame,
          getEffectiveHighlight(
            atFrame,
            opts.focusedEntityId,
            opts.selectedToolType,
            opts.entitiesById,
          ),
        );
        if (mapped) {
          results.push(mapped);
          seenIds.add(mapped.id);
        }
        continue;
      }

      if (childs.length > 1) {
        const sample = childs[0];
        const viewFrames = opts.mViews[sample.data.view_name] as SequenceFrame[] | undefined;
        const viewFrame = viewFrames?.[opts.frameIdx];
        if (viewFrame) {
          const mappedChilds = childs
            .map((ann) =>
              opts.mapForDisplay(
                ann,
                getEffectiveHighlight(
                  ann,
                  opts.focusedEntityId,
                  opts.selectedToolType,
                  opts.entitiesById,
                ),
              ),
            )
            .filter((v): v is TDisplay => v !== undefined);
          const interpolated = opts.interpolateFn(mappedChilds, opts.frameIdx, viewFrame.id);
          if (interpolated) {
            results.push(interpolated);
            seenIds.add(interpolated.id);
          }
        }
      }
    }
  }

  for (const ann of opts.frameAnnotations) {
    if (seenIds.has(ann.id)) continue;
    const mapped = opts.mapForDisplay(
      ann,
      getEffectiveHighlight(ann, opts.focusedEntityId, opts.selectedToolType, opts.entitiesById),
    );
    if (mapped) {
      results.push(mapped);
      seenIds.add(mapped.id);
    }
  }

  return { results, seenIds };
}

// --- Current-frame derived stores ---

export const current_itemBBoxes = reactiveDerived(() => {
  const frameIdx = currentFrameIndex.value;
  const mViews = mediaViews.value;
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const eById = entitiesById.value;

  const { results, seenIds } = collectFrameAnnotations<BBox, BBox>({
    frameAnnotations: _frameBuckets.bboxes.get(frameIdx) ?? [],
    typeFilter: (ann): ann is BBox => ann.is_type(BaseSchema.BBox),
    mapForDisplay: (bbox, hl) => mapBBoxForDisplay(bbox, mViews, hl),
    interpolateFn: boxLinearInterpolation,
    frameIdx,
    doInterpolate: interpolate.value,
    tracks: tracks.value,
    mViews,
    focusedEntityId,
    selectedToolType,
    entitiesById: eById,
  });

  for (const previewBBox of generatedPreviewBBoxes.value) {
    if (previewBBox.ui.frame_index !== frameIdx || seenIds.has(previewBBox.id)) continue;
    const mapped = mapBBoxForDisplay(
      previewBBox,
      mViews,
      getEffectiveHighlight(previewBBox, focusedEntityId, selectedToolType, eById),
    );
    if (mapped) results.push(mapped);
  }

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

  const currentMasks: Mask[] = [];
  for (const maskAtFrame of frameMasks) {
    const mappedMask = mapMaskForDisplay(
      maskAtFrame,
      getEffectiveHighlight(maskAtFrame, focusedEntityId, selectedToolType, eById),
    );
    if (mappedMask) {
      currentMasks.push(mappedMask);
    }
  }

  return currentMasks;
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
