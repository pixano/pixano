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

  import { selectedSegmentationModel } from "$lib/stores/inferenceStores.svelte";
  import { InteractiveSegmenter } from "$lib/segmentation";
  import {
    createErrorSmartSegmentationUiState,
    createIdleSmartSegmentationUiState,
    createPendingSmartSegmentationUiState,
  } from "$lib/segmentation/smartInferenceStatus";
  import {
    brushSettings,
    colorScale,
    embeddings,
    filters,
    imageSmoothing,
    itemBboxes,
    itemKeypoints,
    itemMasks,
    itemMultiPaths,
    modelsUiStore,
    newShape,
    preAnnotationIsActive,
    smartSegmentationUiState,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import {
    ToolType,
    type InteractiveSegmenterAIInput,
    type SelectionTool,
  } from "$lib/tools";
  import { ShapeType, type ImageFilters, type SaveMaskShape, type Shape } from "$lib/types/shapeTypes";
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
  const interactiveSegmenter = new InteractiveSegmenter();
  let smartPreviewMasks = $state<Record<string, SaveMaskShape | null>>({});

  const handleCanvasShapeChange = (shape: Shape) => {
    // Draft creation now stays local in Canvas2D and should not trigger store churn.
    if (shape.status === "creating") return;

    if (
      selectedTool.value?.type === ToolType.Brush &&
      shape.status === "saving" &&
      shape.type === ShapeType.mask &&
      smartPreviewMasks[shape.viewRef.name]
    ) {
      clearSmartPreview(shape.viewRef.name);
      interactiveSegmenter.clear(shape.viewRef);
      smartSegmentationUiState.value = createIdleSmartSegmentationUiState();
    }

    newShape.value = shape as import("$lib/ui").Shape;
  };

  function clearSmartPreview(viewName?: string): void {
    if (viewName) {
      const next = { ...smartPreviewMasks };
      delete next[viewName];
      smartPreviewMasks = next;
      return;
    }
    smartPreviewMasks = {};
  }

  function resetSmartSegmentationFeedback(): void {
    smartSegmentationUiState.value = createIdleSmartSegmentationUiState();
  }

  function resolveImageSource(viewName: string):
    | {
        width: number;
        height: number;
      }
    | null {
    const rawView = selectedItem.views?.[viewName];
    if (!rawView || Array.isArray(rawView)) return null;
    const view = rawView as Image;

    return {
      width: Number(view.data.width),
      height: Number(view.data.height),
    };
  }

  async function handleSmartSegmentationRequest(
    requestId: string,
    request: InteractiveSegmenterAIInput,
  ): Promise<void> {
    const modelSelection = selectedSegmentationModel.value;

    if (request.action === "clear") {
      clearSmartPreview(request.viewRef.name);
      interactiveSegmenter.clear(request.viewRef);
      resetSmartSegmentationFeedback();
      return;
    }

    if (request.action === "confirm") {
      const previewMask = smartPreviewMasks[request.viewRef.name];
      if (previewMask) {
        resetSmartSegmentationFeedback();
        newShape.value = previewMask;
      }
      return;
    }

    if (smartSegmentationUiState.value.phase === "pending") {
      return;
    }

    if (!modelSelection) return;

    const image = resolveImageSource(request.viewRef.name);
    if (!image) return;

    smartSegmentationUiState.value = createPendingSmartSegmentationUiState(
      requestId,
      request.viewRef.name,
    );

    try {
      const prediction = await interactiveSegmenter.predictMask({
        datasetId: selectedItem.ui.datasetId,
        viewRef: request.viewRef,
        itemId: selectedItem.item.id,
        image,
        model: modelSelection.name,
        providerName: modelSelection.provider_name,
        prompt: {
          points: request.prompt.points.map((point) => ({
            x: point.x,
            y: point.y,
            label: point.label as 0 | 1,
          })),
          box: request.prompt.box
            ? {
                x: request.prompt.box.x,
                y: request.prompt.box.y,
                width: request.prompt.box.width,
                height: request.prompt.box.height,
              }
            : null,
        },
      });

      if (smartSegmentationUiState.value.requestId !== requestId) {
        return;
      }

      resetSmartSegmentationFeedback();
      smartPreviewMasks = {
        ...smartPreviewMasks,
        [request.viewRef.name]: prediction?.previewMask ?? null,
      };
    } catch (error) {
      if (smartSegmentationUiState.value.requestId !== requestId) {
        return;
      }

      smartSegmentationUiState.value = createErrorSmartSegmentationUiState(
        requestId,
        request.viewRef.name,
        error,
      );
    }
  }

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
      clearSmartPreview();
      interactiveSegmenter.clear();
      resetSmartSegmentationFeedback();
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

  $effect(() => {
    const toolType = selectedTool.value?.type;
    if (toolType === ToolType.InteractiveSegmenter || toolType === ToolType.Brush) return;
    untrack(() => {
      clearSmartPreview();
      interactiveSegmenter.clear();
      resetSmartSegmentationFeedback();
    });
  });

  $effect(() => {
    void selectedSegmentationModel.value;
    untrack(() => {
      clearSmartPreview();
      interactiveSegmenter.clear();
      resetSmartSegmentationFeedback();
    });
  });

  $effect(() => {
    const shape = newShape.value;
    if (shape.status !== "none" || !shape.shouldReset) return;
    if (shape.resetReason !== "save-confirmed" || shape.resetShapeType !== ShapeType.mask) return;
    const viewRef = shape.resetViewRef;
    if (!viewRef) return;

    untrack(() => {
      clearSmartPreview(viewRef.name);
      interactiveSegmenter.clear(viewRef);
      resetSmartSegmentationFeedback();
    });
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
      multiPaths={itemMultiPaths.value}
      keypoints={itemKeypoints.value}
      filters={filters.value as unknown as ImageFilters}
      canvasSize={resize}
      imageSmoothing={imageSmoothing.value}
      selectedTool={selectedTool.value}
      brushSettings={brushSettings.value}
      newShape={newShape.value}
      {smartPreviewMasks}
      smartInferenceStatus={smartSegmentationUiState.value}
      showSmartPromptCursorOverlay={true}
      onSelectedToolChange={(tool: SelectionTool) => (selectedTool.value = tool)}
      onNewShapeChange={handleCanvasShapeChange}
      onBrushSettingsChange={(settings: BrushSettings) => (brushSettings.value = settings)}
      onAIRequest={(requestId, request) => {
        void handleSmartSegmentationRequest(requestId, request);
      }}
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
