<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  // Import stores and API functions

  import { Canvas2D } from "$components/workspace/canvas2d";
  import { CircleNotch } from "phosphor-svelte";
  import { untrack } from "svelte";

  import {
    brushSettings,
    colorScale,
    embeddings,
    filters,
    imageSmoothing,
    itemBboxes,
    itemKeypoints,
    itemMasks,
    modelsUiStore,
    newShape,
    preAnnotationIsActive,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import type { SelectionTool } from "$lib/tools";
  import type { ImageFilters, Shape } from "$lib/types/shapeTypes";
  import type { WorkspaceViewerItem } from "$lib/types/workspace";
  import { Image, type LoadedImagesPerView } from "$lib/ui";
  import { applyNewShapeEditing } from "$lib/utils/entityAnnotationEditing";
  import { loadImagesFromViews } from "$lib/utils/imageLoadUtils";

  interface Props {
    // Attributes
    selectedItem: WorkspaceViewerItem;
    resize: number;
  }

  interface BrushSettings {
    brushRadius: number;
    lazyRadius: number;
    friction: number;
  }

  let { selectedItem, resize }: Props = $props();

  // Images per view type
  let imagesPerView: LoadedImagesPerView = $state({});
  let loaded: boolean = $state(false); // Loading status of images per view
  let prevSelectedItemId: string = $state("");
  let imageLoadRequestId = 0;
  const hasImages = $derived(Object.keys(imagesPerView).length > 0);

  const handleCanvasShapeChange = (shape: Shape) => {
    // Draft creation now stays local in Canvas2D and should not trigger store churn.
    if (shape.status === "creating") return;
    newShape.value = shape as import("$lib/ui").Shape;
  };

  /**
   * Update the images based on the selected item views.
   */
  const updateImages = async (clearExistingViews = false): Promise<void> => {
    const requestId = ++imageLoadRequestId;
    loaded = false;
    if (clearExistingViews) {
      imagesPerView = {};
    }

    if (!selectedItem.views) {
      imagesPerView = {};
      loaded = true;
      return;
    }

    embeddings.value = {};
    modelsUiStore.update((store) => ({ ...store, yetToLoadEmbedding: true }));
    const nextImages = await loadImagesFromViews(selectedItem.views as Record<string, Image>, {
      sortKeys: true,
      filterImages: true,
    });

    if (requestId !== imageLoadRequestId) return;
    imagesPerView = nextImages;
    loaded = true;
  };

  // Reactive statement to update images when selectedItem changes or the 16 bit filters change
  let prev16BitRange = $state<number[]>([0, 0]);
  $effect(() => {
    const selectedItemId = selectedItem?.item?.id ?? "";
    const next16BitRange = filters.value.u16BitRange;
    const itemChanged = selectedItemId !== prevSelectedItemId;
    const rangeChanged =
      prev16BitRange[0] !== next16BitRange[0] || prev16BitRange[1] !== next16BitRange[1];

    if (itemChanged || rangeChanged) {
      prevSelectedItemId = selectedItemId;
      prev16BitRange = [...next16BitRange];
      void updateImages(itemChanged).catch(() => {
        console.error("Error loading the images.");
      });
    }
  });

  // Reactive statement to update item objects when new shape is being edited and pre-annotation is not active
  $effect(() => {
    const shape = newShape.value;
    const isPreAnnotation = preAnnotationIsActive.value;
    if (shape?.status === "editing" && !isPreAnnotation) {
      untrack(() => {
        applyNewShapeEditing(shape);
      });
    }
  });
</script>

<div class="w-full h-full relative">
  {#if loaded && hasImages}
    <Canvas2D
      {imagesPerView}
      selectedItemId={selectedItem.item.id}
      colorScale={colorScale.value[1]}
      bboxes={itemBboxes.value}
      masks={itemMasks.value}
      keypoints={itemKeypoints.value}
      filters={filters.value as unknown as ImageFilters}
      canvasSize={resize}
      imageSmoothing={imageSmoothing.value}
      selectedTool={selectedTool.value}
      brushSettings={brushSettings.value}
      newShape={newShape.value}
      onSelectedToolChange={(tool: SelectionTool) => (selectedTool.value = tool)}
      onNewShapeChange={handleCanvasShapeChange}
      onBrushSettingsChange={(settings: BrushSettings) => (brushSettings.value = settings)}
    />
  {:else}
    <div class="w-full h-full bg-canvas"></div>
  {/if}

  {#if !loaded}
    <div class="absolute inset-0 z-10 bg-canvas/95 flex items-center justify-center">
      <CircleNotch weight="regular" class="h-10 w-10 animate-spin stroke-white" />
    </div>
  {/if}
</div>
