<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import {
    Check,
    Eraser,
    MinusCircleIcon,
    MousePointer2,
    Paintbrush,
    PencilLine,
    PlusCircleIcon,
    Settings,
    Sparkles,
    Square,
    Wand2Icon,
    X,
  } from "lucide-svelte";
  import { onDestroy, onMount } from "svelte";

  import { ToolType } from "@pixano/canvas2d/src/tools";
  import { SaveShapeType, type SelectionTool } from "@pixano/core";
  import { cn, ConnectToServerModal, IconButton } from "@pixano/core/src";
  import polygon_icon from "@pixano/core/src/assets/lucide_polygon_icon.svg";
  import { pixanoInferenceTracking } from "@pixano/core/src/components/pixano_inference_segmentation/inference";
  import {
    inferenceServerStore,
    segmentationModels,
    selectedSegmentationModelName,
  } from "@pixano/core/src/lib/stores/inferenceStore";

  import { clearHighlighting } from "../lib/api/objectsApi/clearHighlighting";
  import {
    addSmartPointTool,
    brushDrawTool,
    brushEraseTool,
    panTool,
    polygonTool,
    rectangleTool,
    removeSmartPointTool,
    smartRectangleTool,
  } from "../lib/settings/selectionTools";
  import {
    interactiveSegmenterModel,
    merges,
    modelsUiStore,
    newShape,
    selectedTool,
  } from "../lib/stores/datasetItemWorkspaceStores";
  import BrushSettings from "./Toolbar/BrushSettings.svelte";
  import FusionTool from "./Toolbar/FusionTool.svelte";
  import KeyboardShortcuts from "./Toolbar/KeyboardShortcuts.svelte";
  import KeyPointsSelection from "./Toolbar/KeyPointsSelectionTool.svelte";

  export let isVideo: boolean = false;

  let showConnectModal = false;
  let previousSelectedTool: SelectionTool | null = null;
  $: showSmartTools = $selectedTool && $selectedTool.isSmart;
  $: showBrushTools = $selectedTool?.type === ToolType.Brush;
  $: noModelSelected =
    $inferenceServerStore.connected &&
    $segmentationModels.length > 0 &&
    !$selectedSegmentationModelName;

  const clearFusionHighlighting = () => {
    clearHighlighting();
    merges.set({ to_fuse: [], forbids: [] });
  };

  const selectTool = (tool: SelectionTool) => {
    if (tool !== $selectedTool) {
      clearFusionHighlighting();
      selectedTool.set(tool);
    }
  };

  const handleBrushToolClick = () => {
    if (!showBrushTools) {
      selectTool(brushDrawTool);
    } else {
      selectTool(panTool);
    }
  };

  const handleSmartToolClick = () => {
    if (!showSmartTools) {
      selectTool(addSmartPointTool);
      // Open model selection if no model is selected from centralized store
      if ($segmentationModels.length > 0 && !$selectedSegmentationModelName) {
        configSmartToolClick();
      }
    } else selectTool(panTool);
  };

  const onAbort = () => {
    newShape.set({ status: "none", shouldReset: true });
    selectTool(panTool);
  };

  const configSmartToolClick = () => {
    modelsUiStore.update((store) => ({ ...store, currentModalOpen: "selectModel" }));
  };

  const unsubscribeInteractiveSegmenterModel = interactiveSegmenterModel.subscribe((segmenter) => {
    if (segmenter) {
      addSmartPointTool.postProcessor = segmenter;
      removeSmartPointTool.postProcessor = segmenter;
      smartRectangleTool.postProcessor = segmenter;
    }
  });

  onDestroy(unsubscribeInteractiveSegmenterModel);

  onMount(() => {
    if ($selectedTool === undefined) selectedTool.set(panTool);
    clearFusionHighlighting();
  });

  $: {
    if (!previousSelectedTool?.isSmart || !$selectedTool?.isSmart) {
      newShape.set({ status: "none" });
    }
    previousSelectedTool = $selectedTool;
  }

  $: polygonHint = (() => {
    if ($selectedTool?.type !== ToolType.Polygon) return "";
    if ($newShape?.status === "creating" && $newShape?.type === SaveShapeType.mask) {
      if ($newShape.phase === "editing")
        return "Enter: save | Click edge: add point | Click: new polygon/hole | Esc: cancel";
      if ($newShape.phase === "drawing")
        return "Click to add points | Click first point to close | Esc: cancel";
    }
    return "";
  })();
</script>

<div
  class="flex items-center gap-1.5 z-10 bg-card/90 backdrop-blur-md p-0.5 px-1.5 rounded-xl border border-border/40 shadow-sm transition-all duration-500 hover:bg-card hover:border-border/60 group/toolbar"
>
  <!-- Selection & Move Tool Group -->
  <div class="flex items-center gap-0.5">
    <IconButton
      tooltipContent={panTool.name}
      on:click={() => selectTool(panTool)}
      selected={$selectedTool?.type === ToolType.Pan}
      class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
    >
      <MousePointer2 class="h-4.5 w-4.5" />
    </IconButton>
  </div>

  <div class="w-px h-4 bg-border/30 mx-0.5"></div>

  <!-- Drawing Tools Group -->
  <div class="flex items-center gap-0.5">
    <IconButton
      tooltipContent={rectangleTool.name}
      on:click={() => selectTool(rectangleTool)}
      selected={$selectedTool?.type === ToolType.Rectangle && !$selectedTool.isSmart}
      class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
    >
      <Square class="h-4.5 w-4.5" />
    </IconButton>
    <IconButton
      tooltipContent={polygonTool.name}
      on:click={() => selectTool(polygonTool)}
      selected={$selectedTool?.type === ToolType.Polygon}
      class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
    >
      <img src={polygon_icon} alt="polygon icon" class="h-4.5 w-4.5" />
    </IconButton>
  </div>

  <KeyPointsSelection {selectTool} />

  {#if polygonHint}
    <div class="text-xs text-muted-foreground px-2 py-0.5 whitespace-nowrap">
      {polygonHint}
    </div>
  {/if}

  {#if isVideo}
    <FusionTool {selectTool} {clearFusionHighlighting} />
  {/if}

  <div class="w-px h-4 bg-border/30 mx-0.5"></div>

  <!-- Brush Tool Group -->
  <div
    class={cn(
      "flex items-center gap-1 transition-all duration-300 p-0.5 rounded-xl border border-transparent",
      {
        "bg-muted/40 border-border/20 shadow-inner": showBrushTools,
      },
    )}
  >
    <IconButton
      tooltipContent="Brush Tool (B)"
      on:click={handleBrushToolClick}
      class={cn(
        "h-8 w-8 transition-all duration-300 hover:bg-accent/60",
        showBrushTools ? "text-primary" : "text-foreground",
      )}
    >
      <Paintbrush class="h-4.5 w-4.5" />
    </IconButton>
    {#if showBrushTools}
      <div
        class="flex items-center gap-0.5 animate-in fade-in slide-in-from-left-1 duration-500 bg-background/60 backdrop-blur-sm rounded-lg p-0.5 border border-border/40 shadow-sm ml-0.5"
      >
        <IconButton
          tooltipContent="Draw mode (X to toggle)"
          on:click={() => selectTool(brushDrawTool)}
          selected={$selectedTool?.type === ToolType.Brush && $selectedTool.mode === "draw"}
          class="h-8 w-8"
        >
          <PencilLine class="h-4.5 w-4.5" />
        </IconButton>
        <IconButton
          tooltipContent="Erase mode (X to toggle)"
          on:click={() => selectTool(brushEraseTool)}
          selected={$selectedTool?.type === ToolType.Brush && $selectedTool.mode === "erase"}
          class="h-8 w-8"
        >
          <Eraser class="h-4.5 w-4.5" />
        </IconButton>

        <div class="w-px h-3 bg-border/20 mx-0.5"></div>
        <BrushSettings />
      </div>
    {/if}
  </div>

  <div class="w-px h-4 bg-border/30 mx-0.5"></div>

  <!-- Smart Tools Group -->
  <div
    class={cn(
      "flex items-center gap-1 transition-all duration-300 p-0.5 rounded-xl border border-transparent",
      {
        "bg-muted/40 border-border/20 shadow-inner": showSmartTools,
      },
    )}
  >
    <IconButton
      tooltipContent={noModelSelected
        ? "Smart Segmentation — No model selected"
        : "Smart Segmentation"}
      on:click={handleSmartToolClick}
      class={cn(
        "h-8 w-8 transition-all duration-300 hover:bg-accent/60",
        showSmartTools ? "text-primary" : "text-foreground",
      )}
    >
      <Wand2Icon class="h-4.5 w-4.5" />
      {#if noModelSelected && !showSmartTools}
        <span
          class="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-warning animate-pulse"
        />
      {/if}
    </IconButton>
    {#if showSmartTools}
      <div
        class="flex items-center gap-0.5 animate-in fade-in slide-in-from-left-1 duration-500 bg-background/60 backdrop-blur-sm rounded-lg p-0.5 border border-border/40 shadow-sm ml-0.5"
      >
        <IconButton
          tooltipContent={addSmartPointTool.name}
          on:click={() => selectTool(addSmartPointTool)}
          selected={$selectedTool?.type === ToolType.PointSelection && !!$selectedTool.label}
          class="h-8 w-8"
        >
          <PlusCircleIcon class="h-4.5 w-4.5" />
        </IconButton>
        <IconButton
          tooltipContent={removeSmartPointTool.name}
          on:click={() => selectTool(removeSmartPointTool)}
          selected={$selectedTool?.type === ToolType.PointSelection && !$selectedTool.label}
          class="h-8 w-8"
        >
          <MinusCircleIcon class="h-4.5 w-4.5" />
        </IconButton>
        <IconButton
          tooltipContent={smartRectangleTool.name}
          on:click={() => selectTool(smartRectangleTool)}
          selected={$selectedTool?.type === ToolType.Rectangle && $selectedTool.isSmart}
          class="h-8 w-8"
        >
          <Square class="h-4.5 w-4.5" />
        </IconButton>
        {#if isVideo && $pixanoInferenceTracking.mustValidate}
          <div class="w-px h-3 bg-border/20 mx-0.5"></div>
          <IconButton
            tooltipContent={"Track"}
            on:click={() =>
              pixanoInferenceTracking.set({ ...$pixanoInferenceTracking, validated: true })}
            class="h-8 w-8 text-success/80 hover:bg-success/5"
          >
            <Check class="h-4.5 w-4.5" />
          </IconButton>
          <IconButton
            tooltipContent={"Abort tracking (Escape)"}
            on:click={onAbort}
            class="h-8 w-8 text-destructive/80 hover:bg-destructive/5"
          >
            <X class="h-4.5 w-4.5" />
          </IconButton>
        {/if}

        {#if noModelSelected}
          <button
            on:click={configSmartToolClick}
            class="text-xs text-warning dark:text-warning px-1.5 py-0.5 rounded bg-warning/10 hover:bg-warning/20 transition-colors whitespace-nowrap"
          >
            Select model
          </button>
        {/if}

        <div class="w-px h-3 bg-border/20 mx-0.5"></div>
        <IconButton
          tooltipContent={"Settings"}
          on:click={() => configSmartToolClick()}
          class="h-7 w-7 text-foreground hover:bg-accent/60 transition-all duration-200"
        >
          <Settings class="h-4.5 w-4.5" />
        </IconButton>
      </div>
    {/if}
  </div>

  <div class="w-px h-4 bg-border/30 mx-0.5"></div>

  <!-- Status Group -->
  <div class="flex items-center">
    <IconButton
      tooltipContent={$inferenceServerStore.connected
        ? $selectedSegmentationModelName
          ? `Model: ${$selectedSegmentationModelName}`
          : "Connected — No model selected"
        : "Not connected"}
      on:click={() => (showConnectModal = true)}
      class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
    >
      <Sparkles
        size={18}
        class={$inferenceServerStore.connected
          ? $segmentationModels.length > 0
            ? $selectedSegmentationModelName
              ? "text-success/80"
              : "text-warning/70 animate-pulse"
            : "text-warning/60"
          : "text-destructive/40"}
      />
    </IconButton>
  </div>

  <div class="w-px h-4 bg-border/30 mx-0.5"></div>

  <div class="flex items-center">
    <KeyboardShortcuts {isVideo} />
  </div>
</div>

{#if showConnectModal}
  <ConnectToServerModal
    defaultUrl=""
    on:close={() => (showConnectModal = false)}
    on:connected={() => (showConnectModal = false)}
  />
{/if}
