<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { navigating } from "$app/state";
  import { Canvas2D } from "$components/workspace/canvas2d";
  import { Loader2Icon } from "lucide-svelte";
  import { untrack } from "svelte";

  import TimelinePanel from "../VideoPlayer/TimelinePanel.svelte";
  import {
    currentFrameIndex,
    currentItemId,
    imagesPerView,
    lastFrameIndex,
    playbackState,
    videoViewNames,
  } from "$lib/stores/videoStores.svelte";
  import {
    annotations,
    brushSettings,
    colorScale,
    current_itemBBoxes,
    current_itemKeypoints,
    current_itemMasks,
    imageSmoothing,
    newShape,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import { ToolType, type SelectionTool } from "$lib/tools";
  import { DatasetItem, ShapeType, SequenceFrame, type EditShape } from "$lib/ui";
  import {
    tryHighlightSelectionShape,
    updateExistingAnnotation,
  } from "$lib/utils/entityAnnotationEditing";
  import { scrollIntoView } from "$lib/utils/highlightOperations";
  import { saveTo } from "$lib/utils/saveItemUtils";
  import { toggleFusionEntity } from "$lib/utils/videoFusion";
  import { loadInitialFrames, setBufferSpecs } from "$lib/utils/videoOperations";
  import { editKeyItemInTracklet } from "$lib/utils/videoShapeEditing";

  interface Props {
    selectedItem: DatasetItem;
    resize: number;
  }

  interface BrushSettings {
    brushRadius: number;
    lazyRadius: number;
    friction: number;
  }

  let { selectedItem, resize }: Props = $props();

  $effect(() => {
    if (selectedItem) {
      currentFrameIndex.value = 0;
    }
  });

  let inspectorMaxHeight = $state(250);
  let expanding = $state(false);
  let isLoaded = $state(false);
  let loadingCycle = 0;
  let lastLoadedVideoItemId = "";
  const isRouteLoading = $derived(navigating.from !== null);

  const handleCanvasShapeChange = (shape: import("$lib/ui").Shape) => {
    // Draft creation now stays local in Canvas2D and should not trigger store churn.
    if (shape.status === "creating") return;
    newShape.value = shape;
  };

  // ─── Video loading ──────────────────────────────────────────────────────────

  $effect(() => {
    const nextItemId = selectedItem?.item?.id;
    if (!nextItemId || nextItemId === lastLoadedVideoItemId) return;
    lastLoadedVideoItemId = nextItemId;

    const nextViews = selectedItem.views;

    untrack(() => {
      const cycle = ++loadingCycle;
      const viewNames = Object.keys(nextViews);
      const longestView = Math.max(
        ...Object.values(nextViews).map((view) => (view as SequenceFrame[]).length),
      );

      clearInterval(playbackState.value.intervalId);
      playbackState.update((old) => ({
        ...old,
        intervalId: 0,
        isLoaded: false,
        isBuffering: false,
      }));
      isLoaded = false;

      currentItemId.value = nextItemId;
      videoViewNames.value = viewNames;

      lastFrameIndex.value = longestView - 1;
      setBufferSpecs();

      void loadInitialFrames()
        .then(() => {
          if (cycle !== loadingCycle) return;
          isLoaded = true;
          playbackState.update((old) => ({ ...old, isLoaded: true, isBuffering: false }));
        })
        .catch((error) => {
          if (cycle !== loadingCycle) return;
          console.error("Failed to load initial video frames", error);
          isLoaded = false;
          playbackState.update((old) => ({ ...old, isLoaded: false, isBuffering: false }));
        });
    });
  });

  // ─── Shape editing ──────────────────────────────────────────────────────────

  const updateOrCreateShape = (shape: EditShape) => {
    if (tryHighlightSelectionShape(shape, annotations.value)) {
      newShape.value = { status: "none" };
      return;
    }

    if (shape.type === ShapeType.bbox || shape.type === ShapeType.keypoints) {
      const { objects, save_data } = editKeyItemInTracklet(
        annotations.value,
        shape,
        currentFrameIndex.value,
        current_itemBBoxes.value,
        current_itemKeypoints.value,
      );
      annotations.value = objects;
      if (save_data) saveTo(save_data.change_type, save_data.data);
    } else {
      annotations.update((objects) => updateExistingAnnotation(objects, shape));
    }
    newShape.value = { status: "none" };
  };

  $effect(() => {
    const shape = newShape.value;
    if (!shape || shape.status !== "editing") return;

    const toolType = selectedTool.value?.type ?? ToolType.Pan;
    untrack(() => {
      if (toolType !== ToolType.Fusion) {
        updateOrCreateShape(shape);
      } else {
        if (shape.top_entity_id) {
          scrollIntoView(shape.top_entity_id);
        }
      }
    });
  });

  // ─── Inspector resize ───────────────────────────────────────────────────────

  const expand = (e: MouseEvent) => {
    if (expanding) {
      inspectorMaxHeight = document.body.scrollHeight - e.pageY;
    }
  };

  // ─── Fusion merge (passed to Canvas2D) ──────────────────────────────────────

  const merge = (clickedAnn: import("$lib/ui").Annotation) => {
    if (selectedTool.value?.type === ToolType.Fusion) {
      toggleFusionEntity(clickedAnn);
    }
  };
</script>

<section
  class="h-full w-full flex flex-col"
  onmouseup={() => {
    expanding = false;
  }}
  onmousemove={expand}
  role="tab"
  tabindex="0"
>
  <div class="overflow-hidden grow relative">
    {#if !isRouteLoading && isLoaded && current_itemBBoxes.value && current_itemKeypoints.value}
      <Canvas2D
        selectedItemId={selectedItem.item.id}
        imagesPerView={imagesPerView.value}
        colorScale={colorScale.value[1]}
        bboxes={current_itemBBoxes.value}
        masks={current_itemMasks.value}
        keypoints={current_itemKeypoints.value}
        canvasSize={inspectorMaxHeight + resize}
        enableRenderCache={false}
        isPlaybackActive={playbackState.value.intervalId !== 0}
        imageSmoothing={imageSmoothing.value}
        selectedTool={selectedTool.value}
        brushSettings={brushSettings.value}
        newShape={newShape.value}
        onSelectedToolChange={(tool: SelectionTool) => {
          selectedTool.value = tool;
        }}
        onNewShapeChange={(shape) => {
          handleCanvasShapeChange(shape as import("$lib/ui").Shape);
        }}
        onBrushSettingsChange={(settings: BrushSettings) => {
          brushSettings.value = settings;
        }}
        {merge}
      />
      {#if playbackState.value.isBuffering}
        <div class="absolute inset-0 z-10 bg-black/35 flex items-center justify-center pointer-events-none">
          <div class="flex flex-col items-center gap-2 text-white">
            <Loader2Icon class="h-8 w-8 animate-spin" />
            <p class="text-sm">Buffering next frames...</p>
          </div>
        </div>
      {/if}
    {:else}
      <div class="h-full w-full bg-canvas flex items-center justify-center">
        <div class="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2Icon class="h-8 w-8 animate-spin text-white" />
          <p class="text-sm">Loading video frames...</p>
        </div>
      </div>
    {/if}
  </div>
  {#if !isRouteLoading && isLoaded && current_itemBBoxes.value && current_itemKeypoints.value}
    <button
      type="button"
      aria-label="Resize canvas and inspector panels"
      class="h-1 bg-primary-light cursor-row-resize w-full"
      onmousedown={() => {
        expanding = true;
      }}
    ></button>
    <div
      class="h-full grow max-h-[25%] overflow-hidden"
      style={`max-height: ${inspectorMaxHeight}px`}
    >
      <TimelinePanel />
    </div>
  {/if}
</section>
