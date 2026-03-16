/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { untrack } from "svelte";

import { cancelTrackingSession } from "./trackingStore.svelte";
import { resetVideoStores } from "./videoStores.svelte";
import {
  annotations,
  brushSettings,
  canSave,
  confidenceThreshold,
  embeddings,
  entities,
  entityFilters,
  filters,
  generatedPreviewBBoxes,
  highlightedEntity,
  imageSmoothing,
  interactiveSegmenterModel,
  interpolate,
  itemMetas,
  merges,
  modelsUiStore,
  newShape,
  preAnnotationIsActive,
  saveData,
  selectedKeypointsTemplate,
  selectedTool,
  views,
} from "./workspaceBaseStores.svelte";
import { panTool } from "$lib/tools";
import { clearAnnotationMappingCaches } from "$lib/utils/annotationMapping";
import * as utils from "$lib/utils/coreUtils";

export {
  annotations,
  brushSettings,
  canSave,
  confidenceThreshold,
  embeddings,
  entities,
  entityFilters,
  filters,
  generatedPreviewBBoxes,
  highlightedEntity,
  imageSmoothing,
  interactiveSegmenterModel,
  interpolate,
  itemMetas,
  merges,
  modelsUiStore,
  newShape,
  preAnnotationIsActive,
  saveData,
  selectedKeypointsTemplate,
  selectedTool,
  views,
};

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
  resetVideoStores();
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
} from "./annotationDerivedStores.svelte";

export {
  current_itemBBoxes,
  current_itemKeypoints,
  current_itemMasks,
} from "./frameAnnotationStores.svelte";
