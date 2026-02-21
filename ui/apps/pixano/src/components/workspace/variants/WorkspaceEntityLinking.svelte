<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">

  // Imports
  import { untrack } from "svelte";
  import { Loader2Icon } from "lucide-svelte";

  import { Canvas2D } from "$components/workspace/canvas2d";
  import type { ImageFilters, Shape } from "$lib/types/shapeTypes";
  import {
    DatasetItem,
    Image,
    isImage,
    Message,
    TextSpan,
    effectProbe,
    type LoadedImagesPerView,
  } from "$lib/ui";
  import TextSpanArea from "../textCanvas/TextSpanArea.svelte";

  // Import stores and API functions
  import { saveTo } from "$lib/utils/saveItemUtils";
  import { getTopEntity } from "$lib/utils/entityLookupUtils";
  import { highlightEntity } from "$lib/utils/highlightOperations";
  import { applyNewShapeEditing } from "$lib/utils/entityMutations";
  import { loadImagesFromViews } from "$lib/utils/imageLoadUtils";
  import {
    annotations,
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
    textSpans,
    textViews,
  } from "$lib/stores/workspaceStores.svelte";


  interface Props {
    // Attributes
    selectedItem: DatasetItem;
    resize: number;
  }

  let { selectedItem, resize }: Props = $props();

  // Images per view type
  let imagesPerView: LoadedImagesPerView = $state({});
  let loaded: boolean = $state(false); // Loading status of images per view

  // utility vars for resizing with slide bar
  let entityLinkingAreaWidth = $state(700); //default width
  let expanding = $state(false);

  /**
   * Update the images based on the selected item views.
   */
  const updateImages = async (): Promise<void> => {
    if (selectedItem.views) {
      loaded = false;
      embeddings.value = {};
      modelsUiStore.update((store) => ({ ...store, yetToLoadEmbedding: true }));
      const image_views = Object.fromEntries(
        Object.entries(selectedItem.views).filter(([, value]) => isImage(value)),
      ) as Record<string, Image>;
      imagesPerView = await loadImagesFromViews(image_views);
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
        effectProbe("EntityLinkingViewer.applyNewShape", {
          status: shape?.status ?? "none",
          preAnnotationIsActive: isPreAnnotation,
        });
        applyNewShapeEditing(shape);
      });
    }
  });

  const handleMessageContentChange = (
    event: CustomEvent<{
      updatedMessage: Message;
    }>,
  ) => {
    event.preventDefault();

    saveTo("update", event.detail.updatedMessage);
  };

  const handleCreateTemporaryTextSpan = (tempTextSpan: TextSpan) => {
    annotations.update((anns) => [...anns, tempTextSpan]);
  };

  const handleTextSpanClick = (textSpan: TextSpan) => {
    highlightEntity(getTopEntity(textSpan).id, false);
  };

  const expand = (e: MouseEvent) => {
    if (expanding) {
      entityLinkingAreaWidth = Math.max(e.pageX, 180);
    }
  };
</script>

<!-- Render the Canvas2D component with the loaded images or show a loading spinner -->
{#if loaded}
  <div
    class="h-full flex"
    onmouseup={() => {
      expanding = false;
    }}
    onmousemove={expand}
    role="tab"
    tabindex="0"
  >
    <div class="w-full grow overflow-hidden" style={`max-width: ${entityLinkingAreaWidth}px`}>
      <TextSpanArea
        textViews={textViews.value}
        selectedItemId={selectedItem.item.id}
        colorScale={colorScale.value[1]}
        textSpans={textSpans.value}
        newShape={newShape.value}
        onNewShapeChange={(shape) => newShape.value = shape}
        onCreateTemporaryTextSpan={handleCreateTemporaryTextSpan}
        onTextSpanClick={handleTextSpanClick}
      />
    </div>
    <button
      type="button"
      aria-label="Resize text and image panels"
      class="w-1 bg-primary-light cursor-col-resize h-full"
      onmousedown={() => {
        expanding = true;
      }}
></button>
    <div class="overflow-hidden grow">
      <Canvas2D
        {imagesPerView}
        selectedItemId={selectedItem.item.id}
        colorScale={colorScale.value[1]}
        bboxes={itemBboxes.value}
        masks={itemMasks.value}
        keypoints={itemKeypoints.value}
        filters={filters.value as ImageFilters}
        canvasSize={entityLinkingAreaWidth + resize}
        imageSmoothing={imageSmoothing.value}
        selectedTool={selectedTool.value}
        brushSettings={brushSettings.value}
        newShape={newShape.value as Shape}
        onSelectedToolChange={(tool) => selectedTool.value = tool}
        onNewShapeChange={(shape) => newShape.value = shape as import("$lib/ui").Shape}
        onBrushSettingsChange={(settings) => brushSettings.value = settings}
      />
    </div>
  </div>
{:else}
  <div class="w-full h-full flex items-center justify-center">
    <Loader2Icon class="h-10 w-10 animate-spin stroke-white" />
  </div>
{/if}
