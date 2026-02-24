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
import type { SelectionTool } from "$lib/tools";
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

export const newShape = reactiveStore<Shape>(undefined as unknown as Shape);
export const selectedTool = reactiveStore<SelectionTool>(undefined as unknown as SelectionTool);
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
  newShape.value = undefined as unknown as Shape;
  selectedTool.value = undefined as unknown as SelectionTool;
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
  for (const ann of annotations.value) {
    if (ann.is_type(BaseSchema.BBox)) {
      const box = mapBBoxForDisplay(ann as BBox, mViews);
      if (box) bboxes.push(box);
    }
  }
  for (const previewBBox of generatedPreviewBBoxes.value) {
    const box = mapBBoxForDisplay(previewBBox, mViews);
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
  for (const ann of annotations.value) {
    if (ann.is_type(BaseSchema.Mask)) {
      const mask = mapMaskForDisplay(ann as Mask);
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
  for (const ann of annotations.value) {
    if (ann.is_type(BaseSchema.Keypoints)) {
      const kpt = mapKeypointsForDisplay(ann as Keypoints, mViews);
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

const _current_itemBBoxes = $derived.by(() => {
  const bboxes = _itemBboxes;
  const frameIdx = currentFrameIndex.value;
  const trks = _tracks;
  const mViews = _mediaViews;
  const doInterpolate = interpolate.value;
  const previewBBoxIdsForFrame = new Set(
    generatedPreviewBBoxes.value
      .filter((bbox) => bbox.ui.frame_index === frameIdx)
      .map((bbox) => bbox.id),
  );

  const current_bboxes_and_interpolated: BBox[] = [];
  const selectedBBoxIds = new Set<string>();
  const current_tracklets = trks.filter(
    (tracklet) => tracklet.data.start_frame <= frameIdx && tracklet.data.end_frame >= frameIdx,
  );
  for (const tracklet of current_tracklets) {
    const bbox_childs_ids = new Set(
      tracklet.ui.childs?.filter((ann) => ann.is_type(BaseSchema.BBox)).map((bbox) => bbox.id),
    );
    const bbox_childs = bboxes.filter((bbox) => bbox_childs_ids.has(bbox.id));
    const box = bbox_childs.find((box) => box.ui.frame_index === frameIdx);
    if (box) {
      current_bboxes_and_interpolated.push(box);
      selectedBBoxIds.add(box.id);
    } else if (bbox_childs.length > 1 && doInterpolate) {
      const sample_bbox = bbox_childs[0];
      const viewFrames = mViews[sample_bbox.data.view_name] as SequenceFrame[] | undefined;
      const viewFrame = viewFrames?.[frameIdx];
      if (viewFrame) {
        const interpolated_box = boxLinearInterpolation(bbox_childs, frameIdx, viewFrame.id);
        if (interpolated_box) {
          current_bboxes_and_interpolated.push(interpolated_box);
          selectedBBoxIds.add(interpolated_box.id);
        }
      }
    }
  }
  for (const bbox of bboxes) {
    if (!previewBBoxIdsForFrame.has(bbox.id) || selectedBBoxIds.has(bbox.id)) continue;
    current_bboxes_and_interpolated.push(bbox);
  }
  return current_bboxes_and_interpolated;
});
export const current_itemBBoxes = {
  get value() {
    return _current_itemBBoxes;
  },
};

const _current_itemKeypoints = $derived.by(() => {
  const kpts = _itemKeypoints;
  const frameIdx = currentFrameIndex.value;
  const trks = _tracks;
  const mViews = _mediaViews;
  const doInterpolate = interpolate.value;

  const current_kpts_and_interpolated: KeypointAnnotation[] = [];
  const current_tracklets = trks.filter(
    (tracklet) => tracklet.data.start_frame <= frameIdx && tracklet.data.end_frame >= frameIdx,
  );
  for (const tracklet of current_tracklets) {
    const kpt_childs_ids = new Set(
      tracklet.ui.childs?.filter((ann) => ann.is_type(BaseSchema.Keypoints)).map((kpt) => kpt.id),
    );
    const kpt_childs = kpts.filter((kpt) => kpt_childs_ids.has(kpt.id));
    const kpt = kpt_childs.find((kpt) => kpt.ui.frame_index === frameIdx);
    if (kpt) current_kpts_and_interpolated.push(kpt);
    else if (kpt_childs.length > 1 && doInterpolate) {
      const sample_kpt = kpt_childs[0];
      const viewFrames = mViews[sample_kpt.viewRef.name] as SequenceFrame[] | undefined;
      const viewFrame = viewFrames?.[frameIdx];
      if (viewFrame) {
        const interpolated_kpt = keypointsLinearInterpolation(kpt_childs, frameIdx, viewFrame.id);
        if (interpolated_kpt) current_kpts_and_interpolated.push(interpolated_kpt);
      }
    }
  }
  return current_kpts_and_interpolated;
});
export const current_itemKeypoints = {
  get value() {
    return _current_itemKeypoints;
  },
};

const _current_itemMasks = $derived.by(() => {
  const masks = _itemMasks;
  const frameIdx = currentFrameIndex.value;
  const trks = _tracks;

  const current_masks: Mask[] = [];
  const current_tracklets = trks.filter(
    (tracklet) => tracklet.data.start_frame <= frameIdx && tracklet.data.end_frame >= frameIdx,
  );
  for (const tracklet of current_tracklets) {
    const mask_childs_ids = new Set(
      tracklet.ui.childs?.filter((ann) => ann.is_type(BaseSchema.Mask)).map((mask) => mask.id),
    );
    const mask_childs = masks.filter((mask) => mask_childs_ids.has(mask.id));
    const mask = mask_childs.find((mask) => mask.ui.frame_index === frameIdx);
    if (mask) current_masks.push(mask);
  }
  return current_masks;
});
export const current_itemMasks = {
  get value() {
    return _current_itemMasks;
  },
};
