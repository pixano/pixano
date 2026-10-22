/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { untrack } from "svelte";

import {
  colorByCatalogue,
  colorBySettings,
  rememberColorByLearned,
  resetColorBy,
} from "./colorByStore.svelte";
import { reactiveDerived } from "./reactiveStore.svelte";
import { resetTrackingByDetectionSession } from "./trackingByDetectionStore.svelte";
import { cancelTrackingSession } from "./trackingStore.svelte";
import { resetVideoStores } from "./videoStores.svelte";
import {
  annotations,
  brushSettings,
  canSave,
  clearTrackEditing,
  confidenceThreshold,
  editedTrackletId,
  embeddings,
  entities,
  entityFilters,
  filters,
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
  smartSegmentationUiState,
  views,
  workspaceSaveQueue,
} from "./workspaceBaseStores.svelte";
import { paletteOf } from "$lib/coloring/colorBySettings";
import {
  buildColorResolver,
  createEntityColorOrder,
  resolveActiveMode,
  type ColorResolver,
} from "$lib/coloring/colorResolver";
import { panTool } from "$lib/tools";
import { clearAnnotationMappingCaches } from "$lib/utils/annotationMapping";

export {
  annotations,
  brushSettings,
  canSave,
  clearTrackEditing,
  confidenceThreshold,
  editedTrackletId,
  embeddings,
  entities,
  entityFilters,
  filters,
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
  smartSegmentationUiState,
  selectedTool,
  views,
  workspaceSaveQueue,
};

// --- Annotation colors ---

// Palette slots of top-level objects, kept across the records of a workspace session.
let entityColorOrder = $state.raw(createEntityColorOrder());
let lastColorResolver: ColorResolver | null = null;

/**
 * The one place that resolves the color of an object or an annotation, for the "Color by" mode
 * of the open dataset. Annotations are read only when the mode depends on them, and the previous
 * resolver is kept when no color changes, so display-only commits re-render nothing.
 */
export const annotationColors = reactiveDerived<ColorResolver>(() => {
  const settings = colorBySettings.value;
  const mode = resolveActiveMode(colorByCatalogue.value, settings);
  const readsAnnotations = mode.kind === "attribute" && mode.attribute.scope === "annotation";
  const resolver = buildColorResolver(
    {
      mode,
      palette: mode.kind === "attribute" ? paletteOf(settings, mode.attribute.id) : undefined,
      entities: entities.value,
      annotations: readsAnnotations ? annotations.value : [],
      entityOrder: entityColorOrder,
    },
    lastColorResolver,
  );
  lastColorResolver = resolver;
  return resolver;
});

// Remember the categories and the range met, so a value keeps its color on the next records.
$effect.root(() => {
  $effect(() => {
    const pending = annotationColors.value.pendingLearned;
    if (pending) untrack(() => rememberColorByLearned(pending));
  });
});

export function resetEntityColorOrder() {
  entityColorOrder = createEntityColorOrder();
}

export function resetWorkspaceStores() {
  resetVideoStores();
  newShape.value = { status: "none" };
  selectedTool.value = panTool;
  highlightedEntity.value = null;
  annotations.value = [];
  entities.value = [];
  views.value = {};
  merges.value = { to_fuse: [], forbids: [] };
  interactiveSegmenterModel.value = undefined;
  itemMetas.value = undefined;
  preAnnotationIsActive.value = false;
  smartSegmentationUiState.value = {
    phase: "idle",
    requestId: null,
    viewName: null,
    message: "",
  };
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
  workspaceSaveQueue.reset();
  interpolate.value = true;
  confidenceThreshold.value = [0.0];
  entityFilters.value = [];
  clearTrackEditing();
  cancelTrackingSession();
  resetTrackingByDetectionSession();
  resetEntityColorOrder();
  resetColorBy();
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
  itemMultiPaths,
  tracks,
  trackletIdByChildId,
  textSpans,
  messages,
} from "./annotationDerivedStores.svelte";

export {
  current_itemBBoxes,
  current_itemKeypoints,
  current_itemMasks,
  current_itemMultiPaths,
} from "./frameAnnotationStores.svelte";
