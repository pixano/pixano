<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import {
    MinusCircleIcon,
    MousePointer,
    PlusCircleIcon,
    Share2,
    Square,
    Wand2Icon,
  } from "lucide-svelte";
  import { onMount } from "svelte";

  import { ToolType } from "@pixano/canvas2d/src/tools";
  import type { SelectionTool } from "@pixano/core";
  import { cn, IconButton } from "@pixano/core/src";

  import {
    addSmartPointTool,
    panTool,
    polygonTool,
    rectangleTool,
    removeSmartPointTool,
    smartRectangleTool,
  } from "../lib/settings/selectionTools";
  import {
    annotations,
    interactiveSegmenterModel,
    merges,
    modelsUiStore,
    newShape,
    selectedTool,
  } from "../lib/stores/datasetItemWorkspaceStores";
  import FusionTool from "./Toolbar/FusionTool.svelte";
  import KeyPointsSelection from "./Toolbar/KeyPointsSelectionTool.svelte";

  export let isVideo: boolean = false;

  let previousSelectedTool: SelectionTool | null = null;
  $: showSmartTools = $selectedTool && $selectedTool.isSmart;

  const cleanFusion = () => {
    //deselect everything = unhighlight all
    annotations.update((anns) =>
      anns.map((ann) => {
        ann.ui.highlighted = "all";
        ann.ui.displayControl = { ...ann.ui.displayControl, editing: false };
        return ann;
      }),
    );
    merges.set({ to_fuse: [], forbids: [] });
  };

  const selectTool = (tool: SelectionTool) => {
    if (tool !== $selectedTool) {
      cleanFusion();
      selectedTool.set(tool);
    }
  };

  const handleSmartToolClick = () => {
    if (!showSmartTools) {
      selectTool(addSmartPointTool);
      modelsUiStore.update((store) => ({ ...store, currentModalOpen: "selectModel" }));
    } else selectTool(panTool);
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
      <Share2 />
    </IconButton>
    <KeyPointsSelection {selectTool} />
    {#if isVideo}
      <FusionTool {selectTool} {cleanFusion} />
    {/if}
  </div>
  <div
    class={cn("flex items-center gap-4", {
      "bg-slate-200 rounded-sm": showSmartTools,
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
    {/if}
  </div>
</div>
