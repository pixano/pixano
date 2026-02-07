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

<div class="flex gap-4 z-10">
  <div class="flex items-center gap-4">
    <IconButton
      tooltipContent={panTool.name}
      on:click={() => selectTool(panTool)}
      selected={$selectedTool?.type === ToolType.Pan}
    >
      <MousePointer />
    </IconButton>
    <IconButton
      tooltipContent={rectangleTool.name}
      on:click={() => selectTool(rectangleTool)}
      selected={$selectedTool?.type === ToolType.Rectangle && !$selectedTool.isSmart}
    >
      <Square />
    </IconButton>
    <IconButton
      tooltipContent={polygonTool.name}
      on:click={() => selectTool(polygonTool)}
      selected={$selectedTool?.type === ToolType.Polygon}
    >
      <img src={polygon_icon} alt="polygon icon" />
    </IconButton>
    <KeyPointsSelection {selectTool} />
    {#if isVideo}
      <FusionTool {selectTool} {clearFusionHighlighting} />
    {/if}
  </div>
  <div
    class={cn("flex items-center gap-4", {
      "bg-muted rounded-lg": showSmartTools,
    })}
  >
    <IconButton tooltipContent="Use a smart segmentation model" on:click={handleSmartToolClick}>
      <Wand2Icon />
    </IconButton>
    {#if showSmartTools}
      <IconButton
        tooltipContent={addSmartPointTool.name}
        on:click={() => selectTool(addSmartPointTool)}
        selected={$selectedTool?.type === ToolType.PointSelection && !!$selectedTool.label}
      >
        <PlusCircleIcon />
      </IconButton>
      <IconButton
        tooltipContent={removeSmartPointTool.name}
        on:click={() => selectTool(removeSmartPointTool)}
        selected={$selectedTool?.type === ToolType.PointSelection && !$selectedTool.label}
      >
        <MinusCircleIcon />
      </IconButton>
      <IconButton
        tooltipContent={smartRectangleTool.name}
        on:click={() => selectTool(smartRectangleTool)}
        selected={$selectedTool?.type === ToolType.Rectangle && $selectedTool.isSmart}
      >
        <Square />
      </IconButton>
      {#if isVideo && $pixanoInferenceTracking.mustValidate}
        <IconButton
          tooltipContent={"Track"}
          on:click={() =>
            pixanoInferenceTracking.set({ ...$pixanoInferenceTracking, validated: true })}
          selected={false}
        >
          <Check />
        </IconButton>
        <IconButton tooltipContent={"Abort tracking (Escape)"} on:click={onAbort} selected={false}>
          <X />
        </IconButton>
      {/if}

      <div class="w-px -m-3.5 h-full bg-border"></div>
      <IconButton
        tooltipContent={"Smart segmentation model settings"}
        on:click={() => configSmartToolClick()}
      >
        <Settings />
      </IconButton>
    {/if}
  </div>
  <div class="w-px h-8 bg-border self-center"></div>
  <IconButton
    tooltipContent="Inference server connection"
    on:click={() => (showConnectModal = true)}
  >
    <Sparkles
      size={20}
      class={$inferenceServerStore.connected
        ? $inferenceServerStore.models.length > 0
          ? "text-green-500"
          : "text-yellow-500"
        : "text-red-500"}
    />
  </IconButton>
</div>

{#if showConnectModal}
  <ConnectToServerModal
    defaultUrl=""
    on:close={() => (showConnectModal = false)}
    on:connected={() => (showConnectModal = false)}
  />
{/if}
