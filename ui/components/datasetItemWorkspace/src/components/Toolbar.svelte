<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import {
    Check,
    MinusCircleIcon,
    MousePointer,
    PlusCircleIcon,
    Settings,
    Sparkles,
    Square,
    Wand2Icon,
    X,
  } from "lucide-svelte";
  import { onDestroy, onMount } from "svelte";

  import { ToolType } from "@pixano/canvas2d/src/tools";
  import type { SelectionTool } from "@pixano/core";
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
  import FusionTool from "./Toolbar/FusionTool.svelte";
  import KeyPointsSelection from "./Toolbar/KeyPointsSelectionTool.svelte";

  export let isVideo: boolean = false;

  let showConnectModal = false;
  let previousSelectedTool: SelectionTool | null = null;
  $: showSmartTools = $selectedTool && $selectedTool.isSmart;

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
</script>

<div
  class="flex items-center gap-1.5 z-10 bg-background/50 backdrop-blur-md p-0.5 px-1.5 rounded-xl border border-border/40 shadow-sm transition-all duration-500 hover:bg-background/80 hover:border-border/60 group/toolbar"
>
  <!-- Manual Tools Group -->
  <div class="flex items-center gap-0.5">
    <IconButton
      tooltipContent={panTool.name}
      on:click={() => selectTool(panTool)}
      selected={$selectedTool?.type === ToolType.Pan}
      class="h-8 w-8 hover:bg-accent/40 transition-all duration-200"
    >
      <MousePointer class="h-4.5 w-4.5" />
    </IconButton>
    <IconButton
      tooltipContent={rectangleTool.name}
      on:click={() => selectTool(rectangleTool)}
      selected={$selectedTool?.type === ToolType.Rectangle && !$selectedTool.isSmart}
      class="h-8 w-8 hover:bg-accent/40 transition-all duration-200"
    >
      <Square class="h-4.5 w-4.5" />
    </IconButton>
    <IconButton
      tooltipContent={polygonTool.name}
      on:click={() => selectTool(polygonTool)}
      selected={$selectedTool?.type === ToolType.Polygon}
      class="h-8 w-8 hover:bg-accent/40 transition-all duration-200"
    >
      <img src={polygon_icon} alt="polygon icon" class="h-4.5 w-4.5 opacity-70" />
    </IconButton>
    <KeyPointsSelection {selectTool} />
    {#if isVideo}
      <FusionTool {selectTool} {clearFusionHighlighting} />
    {/if}
  </div>

  <div class="w-px h-4 bg-border/30 mx-0.5"></div>

  <!-- Smart Tools Group -->
  <div
    class={cn("flex items-center gap-0.5 transition-all duration-500 px-0.5 py-0.5 rounded-lg", {
      "bg-primary/[0.02] ring-1 ring-primary/5": showSmartTools,
    })}
  >
    <IconButton
      tooltipContent="Smart Segmentation"
      on:click={handleSmartToolClick}
      class={cn(
        "h-8 w-8 transition-all duration-300",
        showSmartTools ? "text-primary" : "text-muted-foreground opacity-50 hover:opacity-100",
      )}
    >
      <Wand2Icon class="h-4.5 w-4.5" />
    </IconButton>
    {#if showSmartTools}
      <div class="flex items-center gap-0.5 animate-in fade-in slide-in-from-left-1 duration-500">
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
            class="h-8 w-8 text-green-600/80 hover:bg-green-50/40"
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

        <div class="w-px h-3 bg-border/20 mx-0.5"></div>
        <IconButton
          tooltipContent={"Settings"}
          on:click={() => configSmartToolClick()}
          class="h-7 w-7 text-muted-foreground opacity-40 hover:opacity-100"
        >
          <Settings class="h-4 w-4" />
        </IconButton>
      </div>
    {/if}
  </div>

  <div class="w-px h-4 bg-border/30 mx-0.5"></div>

  <!-- Status Group -->
  <div class="flex items-center">
    <IconButton
      tooltipContent="Inference status"
      on:click={() => (showConnectModal = true)}
      class="h-8 w-8 hover:bg-accent/40 transition-all duration-200"
    >
      <Sparkles
        size={18}
        class={$inferenceServerStore.connected
          ? $inferenceServerStore.models.length > 0
            ? "text-green-500/80 shadow-[0_0_8px_rgba(34,197,94,0.2)]"
            : "text-yellow-500/60"
          : "text-red-400/40"}
      />
    </IconButton>
  </div>
</div>

{#if showConnectModal}
  <ConnectToServerModal
    defaultUrl=""
    on:close={() => (showConnectModal = false)}
    on:connected={() => (showConnectModal = false)}
  />
{/if}
