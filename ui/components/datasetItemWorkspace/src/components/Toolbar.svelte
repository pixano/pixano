<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import {
    MousePointer,
    Square,
    Share2,
    BrushIcon,
    PlusCircleIcon,
    MinusCircleIcon,
  } from "lucide-svelte";

  import type { SelectionTool } from "@pixano/core";
  import { cn, IconButton } from "@pixano/core/src";

  import MagicIcon from "../assets/MagicIcon.svelte";
  import {
    panTool,
    smartRectangleTool,
    rectangleTool,
    addSmartPointTool,
    removeSmartPointTool,
    polygonTool,
  } from "../lib/settings/selectionTools";
  import {
    interactiveSegmenterModel,
    newShape,
    modelsUiStore,
    selectedTool,
  } from "../lib/stores/datasetItemWorkspaceStores";
  import { onMount } from "svelte";

  import KeyPointsSelection from "./Toolbar/KeyPointsSelectionTool.svelte";

  let previousSelectedTool: SelectionTool | null = null;
  let showSmartTools: boolean = false;

  const selectTool = (tool: SelectionTool) => {
    if (tool !== $selectedTool) selectedTool.set(tool);
  };

  const handleSmartToolClick = () => {
    if (!showSmartTools) {
      selectTool(addSmartPointTool);
      modelsUiStore.update((store) => ({ ...store, currentModalOpen: "selectModel" }));
    } else selectTool(panTool);
    showSmartTools = !showSmartTools;
  };

  interactiveSegmenterModel.subscribe((segmenter) => {
    if (segmenter) {
      addSmartPointTool.postProcessor = segmenter;
      removeSmartPointTool.postProcessor = segmenter;
      smartRectangleTool.postProcessor = segmenter;
    }
  });

  onMount(() => {
    selectTool(panTool);
  });

  $: {
    if (!previousSelectedTool?.isSmart || !$selectedTool?.isSmart) {
      newShape.set({ status: "none" });
    }
    previousSelectedTool = $selectedTool;
  }
</script>

<div class="h-full shadow-md py-4 px-2 w-16 border-l bg-slate-100 z-10">
  <div class="flex items-center flex-col gap-4">
    <IconButton
      tooltipContent={panTool.name}
      on:click={() => selectTool(panTool)}
      selected={$selectedTool?.type === "PAN"}
    >
      <MousePointer />
    </IconButton>
    <IconButton
      tooltipContent={rectangleTool.name}
      on:click={() => selectTool(rectangleTool)}
      selected={$selectedTool?.type === "RECTANGLE" && !$selectedTool.isSmart}
    >
      <Square />
    </IconButton>
    <IconButton
      tooltipContent={polygonTool.name}
      on:click={() => selectTool(polygonTool)}
      selected={$selectedTool?.type === "POLYGON"}
    >
      <Share2 />
    </IconButton>
    <KeyPointsSelection />
  </div>
  <div
    class={cn("flex items-center flex-col gap-4 mt-4", {
      "bg-slate-200 rounded-sm": showSmartTools,
    })}
  >
    <IconButton tooltipContent="Use a smart segmentation model" on:click={handleSmartToolClick}>
      <BrushIcon />
      <MagicIcon />
    </IconButton>
    {#if showSmartTools}
      <IconButton
        tooltipContent={addSmartPointTool.name}
        on:click={() => selectTool(addSmartPointTool)}
        selected={$selectedTool?.type === "POINT_SELECTION" && !!$selectedTool.label}
      >
        <PlusCircleIcon />
        <MagicIcon />
      </IconButton>
      <IconButton
        tooltipContent={removeSmartPointTool.name}
        on:click={() => selectTool(removeSmartPointTool)}
        selected={$selectedTool?.type === "POINT_SELECTION" && !$selectedTool.label}
      >
        <MinusCircleIcon />
        <MagicIcon />
      </IconButton>
      <IconButton
        tooltipContent={smartRectangleTool.name}
        on:click={() => selectTool(smartRectangleTool)}
        selected={$selectedTool?.type === "RECTANGLE" && $selectedTool.isSmart}
      >
        <Square />
        <MagicIcon />
      </IconButton>
    {/if}
  </div>
</div>
