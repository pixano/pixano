<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { navigating } from "$app/state";
  import { Canvas2D } from "$components/workspace/canvas2d";
  import { CircleNotch } from "phosphor-svelte";
  import { untrack } from "svelte";

  import TimelinePanel from "../VideoPlayer/TimelinePanel.svelte";
  import {
    currentFrameIndex,
    currentItemId,
    imagesPerView,
    lastFrameIndex,
    playbackState,
    resetVideoStores,
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
  import {
    isTracking,
    trackingPreviewBBoxes,
    startTrackingSession,
    addTrackingKeyframe,
    startNewTrackingSegment,
    isAwaitingNewSegmentKeyframe,
    setPendingKeyframe,
    confirmPendingKeyframe,
    discardPendingKeyframe,
    hasPendingKeyframe,
    pendingKeyframeIndex,
    cancelTrackingSession,
    finalizeTrackingSession,
  } from "$lib/stores/trackingStore.svelte";
  import { ToolType, type SelectionTool } from "$lib/tools";
  import { ShapeType, SequenceFrame, type EditShape, type SaveRectangleShape } from "$lib/ui";
  import type { WorkspaceViewerItem } from "$lib/types/workspace";
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
    selectedItem: WorkspaceViewerItem;
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
  let lastLoadedVideoKey = "";
  const isRouteLoading = $derived(navigating.from !== null);

  function getSequenceFrameViews(item: WorkspaceViewerItem): Record<string, SequenceFrame[]> {
    const entries = Object.entries(item.views).flatMap(([viewName, view]) => {
      if (!Array.isArray(view) || view.length === 0) {
        return [];
      }
      return [[viewName, view as SequenceFrame[]] as const];
    });
    return Object.fromEntries(entries);
  }

  const handleCanvasShapeChange = (shape: import("$lib/ui").Shape) => {
    // Draft creation now stays local in Canvas2D and should not trigger store churn.
    if (shape.status === "creating") return;

    // Intercept bbox saves to start/extend a tracking session
    if (shape.status === "saving" && shape.type === ShapeType.bbox) {
      const saveShape = shape as SaveRectangleShape;
      const { viewRef, itemId, imageWidth, imageHeight, attrs } = saveShape;

      if (!isTracking.value) {
        startTrackingSession(viewRef.name, viewRef, itemId, imageWidth, imageHeight);
      }

      if (hasPendingKeyframe.value) discardPendingKeyframe();

      const normalizedCoords: [number, number, number, number] = [
        attrs.x / imageWidth,
        attrs.y / imageHeight,
        attrs.width / imageWidth,
        attrs.height / imageHeight,
      ];
      addTrackingKeyframe(currentFrameIndex.value, normalizedCoords);

      // Prevent SaveShapeForm from appearing
      newShape.value = { status: "none", shouldReset: true };
      return;
    }

    newShape.value = shape;
  };

  // ─── Video loading ──────────────────────────────────────────────────────────

  $effect(() => {
    const nextItemId = selectedItem?.item?.id;
    if (!nextItemId) return;

    const datasetId = selectedItem.ui.datasetId;
    const nextViews = getSequenceFrameViews(selectedItem);
    const viewNames = Object.keys(nextViews);
    const longestView = viewNames.length
      ? Math.max(...Object.values(nextViews).map((view) => view.length))
      : 0;
    const nextLoadKey = `${nextItemId}:${viewNames.map((viewName) => `${viewName}:${nextViews[viewName].length}`).join("|")}`;
    if (!viewNames.length || longestView <= 0) {
      lastLoadedVideoKey = "";
      isLoaded = false;
      resetVideoStores();
      return;
    }
    if (nextLoadKey === lastLoadedVideoKey) return;
    lastLoadedVideoKey = nextLoadKey;

    untrack(() => {
      const cycle = ++loadingCycle;

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

      void loadInitialFrames(datasetId)
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
        current_itemKeypoints.value as any,
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
      // Edit-during-tracking: stage as pending keyframe (user confirms with T)
      // editCoords from BBox2D are already normalized [0,1]
      if (isTracking.value && shape.type === ShapeType.bbox) {
        const editCoords = (shape as EditShape & { coords: number[] }).coords;
        setPendingKeyframe(currentFrameIndex.value,
          [editCoords[0], editCoords[1], editCoords[2], editCoords[3]]);
        newShape.value = { status: "none" };
        return;
      }

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

  // ─── Tracking: merged bboxes (existing + preview) ─────────────────────────

  const mergedBBoxes = $derived([
    ...(current_itemBBoxes.value ?? []),
    ...(newShape.value?.status === "saving" ? [] : trackingPreviewBBoxes.value),
  ]);

  // ─── Tracking: keyboard handler ───────────────────────────────────────────

  const handleTrackingKeydown = (event: KeyboardEvent) => {
    if (!isTracking.value) return;
    const tag = (event.target as HTMLElement)?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

    if (event.key === "n" || event.key === "N") {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (hasPendingKeyframe.value) confirmPendingKeyframe();
      startNewTrackingSegment();
      return;
    }
    if (event.key === "t" || event.key === "T") {
      if (hasPendingKeyframe.value) {
        event.preventDefault();
        event.stopImmediatePropagation();
        confirmPendingKeyframe();
        return;
      }
      return; // no pending → let Canvas2D handle T for rectangle draft
    }
    if (event.key === "Enter") {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (hasPendingKeyframe.value) confirmPendingKeyframe();
      const saveShape = finalizeTrackingSession();
      if (saveShape) newShape.value = saveShape;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      cancelTrackingSession();
    }
  };

  // ─── Tracking: discard pending edit on frame change ─────────────────────

  $effect(() => {
    const currentFrame = currentFrameIndex.value;
    const pendingFrame = pendingKeyframeIndex.value;
    if (pendingFrame !== null && pendingFrame !== currentFrame) {
      untrack(() => discardPendingKeyframe());
    }
  });

  // ─── Tracking: cancel on tool switch away from Rectangle ──────────────────

  $effect(() => {
    const toolType = selectedTool.value?.type;
    if (isTracking.value && toolType !== ToolType.Rectangle) {
      untrack(() => cancelTrackingSession());
    }
  });

</script>

<svelte:window onkeydown={handleTrackingKeydown} />

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
        confirmKeys={["t", "T"]}
        selectedItemId={selectedItem.item.id}
        imagesPerView={imagesPerView.value}
        colorScale={colorScale.value[1]}
        bboxes={mergedBBoxes}
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
            <CircleNotch weight="regular" class="h-8 w-8 animate-spin" />
            <p class="text-sm">Buffering next frames...</p>
          </div>
        </div>
      {/if}
      {#if isTracking.value}
        <div class="absolute top-2 left-1/2 -translate-x-1/2 z-20 rounded bg-amber-600/90 px-3 py-1 text-xs text-white shadow pointer-events-none select-none">
          {#if hasPendingKeyframe.value}
            Drag to adjust &middot; Press T to confirm as keyframe &middot; Navigate away to discard
          {:else if isAwaitingNewSegmentKeyframe.value}
            New segment started &middot; Navigate to a frame and draw a bbox to begin
          {:else}
            Draw or edit on a frame and press T &middot; N for new segment &middot; Enter to save &middot; Escape to cancel
          {/if}
        </div>
      {/if}
    {:else}
      <div class="h-full w-full bg-canvas flex items-center justify-center">
        <div class="flex flex-col items-center gap-3 text-muted-foreground">
          <CircleNotch weight="regular" class="h-8 w-8 animate-spin text-white" />
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
      class="h-full grow max-h-[28%] overflow-hidden border-t border-border/40 bg-card/90"
      style={`max-height: ${inspectorMaxHeight}px`}
    >
      <TimelinePanel />
    </div>
  {/if}
</section>
