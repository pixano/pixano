<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  // Import stores and API functions

  import { Canvas2D } from "$components/workspace/canvas2d";
  import { Loader2Icon } from "lucide-svelte";
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
  import type { ImageFilters, Shape } from "$lib/types/shapeTypes";
  import { DatasetItem, Image, type LoadedImagesPerView } from "$lib/ui";
  import { applyNewShapeEditing } from "$lib/utils/entityMutations";
  import { loadImagesFromViews } from "$lib/utils/imageLoadUtils";

  interface Props {
    // Attributes
    selectedItem: DatasetItem;
    resize: number;
  }

  let { selectedItem, resize }: Props = $props();

  // Images per view type
  let imagesPerView: LoadedImagesPerView = $state({});
  let loaded: boolean = $state(false); // Loading status of images per view

  const handleCanvasShapeChange = (shape: Shape) => {
    // Draft creation now stays local in Canvas2D and should not trigger store churn.
    if (shape.status === "creating") return;
    newShape.value = shape as import("$lib/ui").Shape;
  };

  /**
   * Update the images based on the selected item views.
   */
  const updateImages = async (): Promise<void> => {
    if (selectedItem.views) {
      loaded = false;
      embeddings.value = {};
      modelsUiStore.update((store) => ({ ...store, yetToLoadEmbedding: true }));
      imagesPerView = await loadImagesFromViews(selectedItem.views as Record<string, Image>, {
        useNativeUrl: true,
        sortKeys: true,
        filterImages: true,
      });
      loaded = true;
    }
  };

  // Reactive statement to update images when selectedItem changes or the 16 bit filters change
  let prev16BitRange: number[] = $state([]);
  $effect(() => {
    if (selectedItem || filters.value.u16BitRange) {
      if (
        prev16BitRange[0] !== filters.value.u16BitRange[0] ||
        prev16BitRange[1] !== filters.value.u16BitRange[1]
      ) {
        updateImages().catch(() => {
          console.error("Error loading the images.");
        });
        prev16BitRange = [...filters.value.u16BitRange];
      }
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

<!-- Render the Canvas2D component with the loaded images or show a loading spinner -->
{#if loaded}
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
    newShape={newShape.value as Shape}
    onSelectedToolChange={(tool) => (selectedTool.value = tool)}
    onNewShapeChange={handleCanvasShapeChange}
    onBrushSettingsChange={(settings) => (brushSettings.value = settings)}
  />
{:else}
  <div class="w-full h-full flex items-center justify-center">
    <Loader2Icon class="h-10 w-10 animate-spin stroke-white" />
  </div>
{/if}
