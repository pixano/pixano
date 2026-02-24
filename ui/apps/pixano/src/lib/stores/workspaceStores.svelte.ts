/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as ort from "onnxruntime-web";
import { untrack } from "svelte";

import { reactiveStore } from "./reactiveStore.svelte";
import { currentFrameIndex } from "./videoStores.svelte";
import type { InteractiveImageSegmenter } from "$lib/models";
import { panTool, ToolType, type SelectionTool } from "$lib/tools";
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
  Track,
  View,
  type SaveItem,
} from "$lib/types/dataset";
import type { KeypointAnnotation, Shape } from "$lib/types/shapeTypes";
import type {
  EntityFilter,
  Filters,
  ItemsMeta,
  Merges,
  ModelSelection,
  MView,
} from "$lib/types/workspace";
import {
  mapBBoxForDisplay,
  mapKeypointsForDisplay,
  mapMaskForDisplay,
} from "$lib/utils/annotationMapping";
import * as utils from "$lib/utils/coreUtils";
import { boxLinearInterpolation, keypointsLinearInterpolation } from "$lib/utils/interpolation";

// --- Writable stores as reactive objects ---

export const newShape = reactiveStore<Shape>({ status: "none" });
export const selectedTool = reactiveStore<SelectionTool>(panTool);
export const highlightedEntity = reactiveStore<string | null>(null);
export const annotations = reactiveStore<Annotation[]>([]);
export const generatedPreviewBBoxes = reactiveStore<BBox[]>([]);
export const entities = reactiveStore<Entity[]>([]);
export const views = reactiveStore<Record<string, View | View[]>>({});
export const merges = reactiveStore<Merges>({ to_fuse: [], forbids: [] });
export const interactiveSegmenterModel = reactiveStore<InteractiveImageSegmenter | undefined>(
  undefined,
);
export const itemMetas = reactiveStore<ItemsMeta | undefined>(undefined);
export const preAnnotationIsActive = reactiveStore<boolean>(false);
export const modelsUiStore = reactiveStore<ModelSelection>({
  currentModalOpen: "none",
  selectedModelName: "",
  selectedTableName: "",
  yetToLoadEmbedding: true,
});
export const embeddings = reactiveStore<Record<string, ort.Tensor>>({});
export const filters = reactiveStore<Filters>({
  brightness: 0,
  contrast: 0,
  equalizeHistogram: false,
  redRange: [0, 255],
  greenRange: [0, 255],
  blueRange: [0, 255],
  u16BitRange: [0, 65535],
});
export const imageSmoothing = reactiveStore<boolean>(true);
export const brushSettings = reactiveStore({ brushRadius: 20, lazyRadius: 10, friction: 0.15 });
export const selectedKeypointsTemplate = reactiveStore<KeypointAnnotation["template_id"] | null>(
  null,
);
export const saveData = reactiveStore<SaveItem[]>([]);

export const canSave = {
  get value() {
    return saveData.value.length > 0;
  },
};

export const interpolate = reactiveStore<boolean>(false);
export const confidenceThreshold = reactiveStore<number[]>([0.0]);
export const entityFilters = reactiveStore<EntityFilter[]>([]);

// --- Color scale (accumulative derived with $effect + untrack) ---

type ColorScale = [Array<string>, (id: string) => string];

const initialColorScale: ColorScale = [[], utils.ordinalColorScale([])];
let _colorScale = $state<ColorScale>(initialColorScale);

$effect.root(() => {
  $effect(() => {
    const ents = entities.value;
    const old = untrack(() => _colorScale);
    let allIds = ents.filter((ent) => ent.data.parent_id === "").map((obj) => obj.id);
    if (old) {
      allIds = [...old[0], ...allIds];
      allIds = [...new Set(allIds)];
    }
    // Guard: skip write if IDs unchanged
    if (old && old[0].length === allIds.length && old[0].every((id, i) => allIds[i] === id)) {
      return;
    }
    _colorScale = [allIds, utils.ordinalColorScale(allIds)];
  });
});

export const colorScale = {
  get value() {
    return _colorScale;
  },
};

export function resetColorScale() {
  _colorScale = initialColorScale;
}

export function resetWorkspaceStores() {
  newShape.value = { status: "none" };
  selectedTool.value = panTool;
  highlightedEntity.value = null;
  annotations.value = [];
  generatedPreviewBBoxes.value = [];
  entities.value = [];
  views.value = {};
  merges.value = { to_fuse: [], forbids: [] };
  interactiveSegmenterModel.value = undefined;
  itemMetas.value = undefined;
  preAnnotationIsActive.value = false;
  modelsUiStore.value = {
    currentModalOpen: "none",
    selectedModelName: "",
    selectedTableName: "",
    yetToLoadEmbedding: true,
  };
  embeddings.value = {};
  filters.value = {
    brightness: 0,
    contrast: 0,
    equalizeHistogram: false,
    redRange: [0, 255],
    greenRange: [0, 255],
    blueRange: [0, 255],
    u16BitRange: [0, 65535],
  };
  imageSmoothing.value = true;
  brushSettings.value = { brushRadius: 20, lazyRadius: 10, friction: 0.15 };
  selectedKeypointsTemplate.value = null;
  saveData.value = [];
  interpolate.value = false;
  confidenceThreshold.value = [0.0];
  entityFilters.value = [];
  resetColorScale();
}

// --- Derived stores (cached via $derived.by) ---

const _mediaViews = $derived.by(() => {
  const mediaViewsResult: MView = {};
  for (const [key, view] of Object.entries(views.value)) {
    if (isMediaView(view)) {
      mediaViewsResult[key] = view;
    }
  }
  return mediaViewsResult;
});
export const mediaViews = {
  get value() {
    return _mediaViews;
  },
};

const _textViews = $derived.by(() => Object.values(views.value).filter((view) => isTextView(view)));
export const textViews = {
  get value() {
    return _textViews;
  },
};

const _itemBboxes = $derived.by(() => {
  const bboxes: BBox[] = [];
  const mViews = _mediaViews;
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const entitiesById =
    selectedToolType === ToolType.Pan && focusedEntityId
      ? new Map(entities.value.map((entity) => [entity.id, entity]))
      : null;

  for (const ann of annotations.value) {
    if (ann.is_type(BaseSchema.BBox)) {
      const bbox = ann as BBox;
      const box = mapBBoxForDisplay(
        bbox,
        mViews,
        getEffectiveHighlight(bbox, focusedEntityId, selectedToolType, entitiesById),
      );
      if (box) bboxes.push(box);
    }
  }
  for (const previewBBox of generatedPreviewBBoxes.value) {
    const box = mapBBoxForDisplay(
      previewBBox,
      mViews,
      getEffectiveHighlight(previewBBox, focusedEntityId, selectedToolType, entitiesById),
    );
    if (box) bboxes.push(box);
  }
  return bboxes;
});
export const itemBboxes = {
  get value() {
    return _itemBboxes;
  },
};

const _itemMasks = $derived.by(() => {
  const masks: Mask[] = [];
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const entitiesById =
    selectedToolType === ToolType.Pan && focusedEntityId
      ? new Map(entities.value.map((entity) => [entity.id, entity]))
      : null;

  for (const ann of annotations.value) {
    if (ann.is_type(BaseSchema.Mask)) {
      const rawMask = ann as Mask;
      const mask = mapMaskForDisplay(
        rawMask,
        getEffectiveHighlight(rawMask, focusedEntityId, selectedToolType, entitiesById),
      );
      if (mask) masks.push(mask);
    }
  }
  return masks;
});
export const itemMasks = {
  get value() {
    return _itemMasks;
  },
};

const _itemKeypoints = $derived.by(() => {
  const mViews = _mediaViews;
  const m_keypoints: KeypointAnnotation[] = [];
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const entitiesById =
    selectedToolType === ToolType.Pan && focusedEntityId
      ? new Map(entities.value.map((entity) => [entity.id, entity]))
      : null;

  for (const ann of annotations.value) {
    if (ann.is_type(BaseSchema.Keypoints)) {
      const keypoint = ann as Keypoints;
      const kpt = mapKeypointsForDisplay(
        keypoint,
        mViews,
        getEffectiveHighlight(keypoint, focusedEntityId, selectedToolType, entitiesById),
      );
      if (kpt) m_keypoints.push(kpt);
    }
  }
  return m_keypoints;
});
export const itemKeypoints = {
  get value() {
    return _itemKeypoints;
  },
};

const _tracks = $derived.by(
  () =>
    annotations.value.filter((annotation) => annotation.is_type(BaseSchema.Tracklet)) as Track[],
);
export const tracks = {
  get value() {
    return _tracks;
  },
};

const _textSpans = $derived.by(
  () =>
    annotations.value.filter((annotation) => annotation.is_type(BaseSchema.TextSpan)) as TextSpan[],
);
export const textSpans = {
  get value() {
    return _textSpans;
  },
};

const _messages = $derived.by(
  () =>
    annotations.value.filter((annotation) => annotation.is_type(BaseSchema.Message)) as Message[],
);
export const messages = {
  get value() {
    return _messages;
  },
};

const _conversations = $derived.by(() =>
  entities.value.filter((entity) => entity.is_type(BaseSchema.Conversation)),
);
export const conversations = {
  get value() {
    return _conversations;
  },
};

type HighlightState = "all" | "self" | "none";

function getTopEntityId(annotation: Annotation, entitiesById: Map<string, Entity>): string {
  const topEntityId = annotation.ui.top_entities?.[0]?.id;
  if (topEntityId) return topEntityId;

  let entityId = annotation.data.entity_id;
  let entity = entitiesById.get(entityId);
  while (entity && entity.data.parent_id !== "") {
    entityId = entity.data.parent_id;
    entity = entitiesById.get(entityId);
  }
  return entityId;
}

function getEffectiveHighlight(
  annotation: Annotation,
  focusedEntityId: string | null,
  selectedToolType: ToolType,
  entitiesById: Map<string, Entity> | null,
): HighlightState {
  const currentHighlight = annotation.ui.displayControl.highlighted;
  if (
    selectedToolType !== ToolType.Pan ||
    !focusedEntityId ||
    entitiesById === null
  ) {
    return currentHighlight;
  }
  return getTopEntityId(annotation, entitiesById) === focusedEntityId
    ? "self"
    : currentHighlight === "none"
      ? "none"
      : "all";
}

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
};

const _frameBuckets = $derived.by<FrameBuckets>(() => {
  const bboxes = new Map<number, BBox[]>();
  const keypoints = new Map<number, Keypoints[]>();
  const masks = new Map<number, Mask[]>();

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
    }
  }

  return { bboxes, keypoints, masks };
});

const _current_itemBBoxes = $derived.by(() => {
  const frameIdx = currentFrameIndex.value;
  const trks = _tracks;
  const mViews = _mediaViews;
  const doInterpolate = interpolate.value;
  const frameBboxes = _frameBuckets.bboxes.get(frameIdx) ?? [];
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const entitiesById =
    selectedToolType === ToolType.Pan && focusedEntityId
      ? new Map(entities.value.map((entity) => [entity.id, entity]))
      : null;

  const currentBboxesAndInterpolated: BBox[] = [];
  const selectedBBoxIds = new Set<string>();
  if (doInterpolate) {
    const currentTracklets = trks.filter(
      (tracklet) => tracklet.data.start_frame <= frameIdx && tracklet.data.end_frame >= frameIdx,
    );

    for (const tracklet of currentTracklets) {
      const bboxChilds = (tracklet.ui.childs ?? []).filter((ann): ann is BBox =>
        ann.is_type(BaseSchema.BBox),
      );

      const boxAtFrame = bboxChilds.find((box) => box.ui.frame_index === frameIdx);
      if (boxAtFrame) {
        const mappedBox = mapBBoxForDisplay(
          boxAtFrame,
          mViews,
          getEffectiveHighlight(boxAtFrame, focusedEntityId, selectedToolType, entitiesById),
        );
        if (mappedBox) {
          currentBboxesAndInterpolated.push(mappedBox);
          selectedBBoxIds.add(mappedBox.id);
        }
        continue;
      }

      if (bboxChilds.length > 1) {
        const sample_bbox = bboxChilds[0];
        const viewFrames = mViews[sample_bbox.data.view_name] as SequenceFrame[] | undefined;
        const viewFrame = viewFrames?.[frameIdx];
        if (viewFrame) {
          const mappedBboxChilds = bboxChilds
            .map((bbox) =>
              mapBBoxForDisplay(
                bbox,
                mViews,
                getEffectiveHighlight(bbox, focusedEntityId, selectedToolType, entitiesById),
              ),
            )
            .filter((bbox): bbox is BBox => bbox !== undefined);
          const interpolated_box = boxLinearInterpolation(mappedBboxChilds, frameIdx, viewFrame.id);
          if (interpolated_box) {
            currentBboxesAndInterpolated.push(interpolated_box);
            selectedBBoxIds.add(interpolated_box.id);
          }
        }
      }
    }
  }

  for (const bbox of frameBboxes) {
    if (selectedBBoxIds.has(bbox.id)) continue;

    const mappedBBox = mapBBoxForDisplay(
      bbox,
      mViews,
      getEffectiveHighlight(bbox, focusedEntityId, selectedToolType, entitiesById),
    );
    if (mappedBBox) {
      currentBboxesAndInterpolated.push(mappedBBox);
      selectedBBoxIds.add(mappedBBox.id);
    }
  }

  for (const previewBBox of generatedPreviewBBoxes.value) {
    if (previewBBox.ui.frame_index !== frameIdx || selectedBBoxIds.has(previewBBox.id)) continue;
    const mappedPreviewBBox = mapBBoxForDisplay(
      previewBBox,
      mViews,
      getEffectiveHighlight(previewBBox, focusedEntityId, selectedToolType, entitiesById),
    );
    if (mappedPreviewBBox) {
      currentBboxesAndInterpolated.push(mappedPreviewBBox);
    }
  }

  return currentBboxesAndInterpolated;
});
export const current_itemBBoxes = {
  get value() {
    return _current_itemBBoxes;
  },
};

const _current_itemKeypoints = $derived.by(() => {
  const frameIdx = currentFrameIndex.value;
  const trks = _tracks;
  const mViews = _mediaViews;
  const doInterpolate = interpolate.value;
  const frameKeypoints = _frameBuckets.keypoints.get(frameIdx) ?? [];
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const entitiesById =
    selectedToolType === ToolType.Pan && focusedEntityId
      ? new Map(entities.value.map((entity) => [entity.id, entity]))
      : null;

  const currentKptsAndInterpolated: KeypointAnnotation[] = [];
  const selectedKptIds = new Set<string>();
  if (doInterpolate) {
    const currentTracklets = trks.filter(
      (tracklet) => tracklet.data.start_frame <= frameIdx && tracklet.data.end_frame >= frameIdx,
    );

    for (const tracklet of currentTracklets) {
      const keypointChilds = (tracklet.ui.childs ?? []).filter((ann): ann is Keypoints =>
        ann.is_type(BaseSchema.Keypoints),
      );

      const keypointAtFrame = keypointChilds.find((kpt) => kpt.ui.frame_index === frameIdx);
      if (keypointAtFrame) {
        const mappedKeypoint = mapKeypointsForDisplay(
          keypointAtFrame,
          mViews,
          getEffectiveHighlight(keypointAtFrame, focusedEntityId, selectedToolType, entitiesById),
        );
        if (mappedKeypoint) {
          currentKptsAndInterpolated.push(mappedKeypoint);
          selectedKptIds.add(mappedKeypoint.id);
        }
        continue;
      }

      if (keypointChilds.length > 1) {
        const sample_kpt = keypointChilds[0];
        const viewFrames = mViews[sample_kpt.data.view_name] as SequenceFrame[] | undefined;
        const viewFrame = viewFrames?.[frameIdx];
        if (viewFrame) {
          const mappedKeypointChilds = keypointChilds
            .map((kpt) =>
              mapKeypointsForDisplay(
                kpt,
                mViews,
                getEffectiveHighlight(kpt, focusedEntityId, selectedToolType, entitiesById),
              ),
            )
            .filter((kpt): kpt is KeypointAnnotation => kpt !== undefined);
          const interpolated_kpt = keypointsLinearInterpolation(
            mappedKeypointChilds,
            frameIdx,
            viewFrame.id,
          );
          if (interpolated_kpt) {
            currentKptsAndInterpolated.push(interpolated_kpt);
            selectedKptIds.add(interpolated_kpt.id);
          }
        }
      }
    }
  }

  for (const keypoint of frameKeypoints) {
    if (selectedKptIds.has(keypoint.id)) continue;
    const mappedKeypoint = mapKeypointsForDisplay(
      keypoint,
      mViews,
      getEffectiveHighlight(keypoint, focusedEntityId, selectedToolType, entitiesById),
    );
    if (mappedKeypoint) {
      currentKptsAndInterpolated.push(mappedKeypoint);
    }
  }

  return currentKptsAndInterpolated;
});
export const current_itemKeypoints = {
  get value() {
    return _current_itemKeypoints;
  },
};

const _current_itemMasks = $derived.by(() => {
  const frameIdx = currentFrameIndex.value;
  const frameMasks = _frameBuckets.masks.get(frameIdx) ?? [];
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const focusedEntityId = highlightedEntity.value;
  const entitiesById =
    selectedToolType === ToolType.Pan && focusedEntityId
      ? new Map(entities.value.map((entity) => [entity.id, entity]))
      : null;

  const currentMasks: Mask[] = [];
  for (const maskAtFrame of frameMasks) {
    const mappedMask = mapMaskForDisplay(
      maskAtFrame,
      getEffectiveHighlight(maskAtFrame, focusedEntityId, selectedToolType, entitiesById),
    );
    if (mappedMask) {
      currentMasks.push(mappedMask);
    }
  }

  return currentMasks;
});
export const current_itemMasks = {
  get value() {
    return _current_itemMasks;
  },
};
