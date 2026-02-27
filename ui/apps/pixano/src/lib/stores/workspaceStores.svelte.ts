/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as ort from "onnxruntime-web";
import { untrack } from "svelte";

import { reactiveStore, reactiveRawStore } from "./reactiveStore.svelte";
import { cancelTrackingSession } from "./trackingStore.svelte";
import type { InteractiveImageSegmenter } from "$lib/models";
import { panTool, type SelectionTool } from "$lib/tools";
import {
  Annotation,
  BBox,
  Entity,
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
} from "$lib/types/workspace";
import { clearAnnotationMappingCaches } from "$lib/utils/annotationMapping";
import * as utils from "$lib/utils/coreUtils";

// --- Writable stores as reactive objects ---

export const newShape = reactiveStore<Shape>({ status: "none" });
export const selectedTool = reactiveStore<SelectionTool>(panTool);
export const highlightedEntity = reactiveStore<string | null>(null);
export const annotations = reactiveStore<Annotation[]>([]);
export const generatedPreviewBBoxes = reactiveStore<BBox[]>([]);
export const entities = reactiveStore<Entity[]>([]);
export const views = reactiveStore<Record<string, View | View[]>>({});
export const merges = reactiveStore<Merges>({ to_fuse: [], forbids: [] });
export const interactiveSegmenterModel = reactiveRawStore<InteractiveImageSegmenter | undefined>(
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
export const embeddings = reactiveRawStore<Record<string, ort.Tensor>>({});
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

export const interpolate = reactiveStore<boolean>(true);
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
  interpolate.value = true;
  confidenceThreshold.value = [0.0];
  entityFilters.value = [];
  cancelTrackingSession();
  resetColorScale();
  clearAnnotationMappingCaches();
}

// --- Re-exports from extracted modules ---
// Consumers can continue importing from this file.

export {
  mediaViews,
  textViews,
  itemBboxes,
  itemMasks,
  itemKeypoints,
  tracks,
  textSpans,
  messages,
  conversations,
} from "./annotationDerivedStores.svelte";

export {
  current_itemBBoxes,
  current_itemKeypoints,
  current_itemMasks,
} from "./frameAnnotationStores.svelte";
