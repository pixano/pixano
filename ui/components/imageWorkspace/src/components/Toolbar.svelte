<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */
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
    modelsStore,
  } from "../lib/stores/imageWorkspaceStores";
  import { onMount } from "svelte";

  export let selectedTool: SelectionTool | null;
  let previousSelectedTool: SelectionTool | null = null;
  let showSmartTools: boolean = false;

  const selectTool = (tool: SelectionTool | null) => {
    if (tool !== selectedTool) selectedTool = tool;
  };

  const handleSmartToolClick = () => {
    if (!showSmartTools) {
      selectTool(addSmartPointTool);
      modelsStore.update((store) => ({ ...store, currentModalOpen: "selectModel" }));
    } else selectTool(null);
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
    if (!previousSelectedTool?.isSmart || !selectedTool?.isSmart) {
      newShape.set({ status: "none" });
    }
    previousSelectedTool = selectedTool;
  }
</script>

<div class="h-full shadow-md bg-popover py-4 px-2 w-16 border-l border-slate-200 z-10">
  <div class="flex items-center flex-col gap-4">
    <IconButton
      tooltipContent={panTool.name}
      on:click={() => selectTool(panTool)}
      selected={selectedTool?.type === "PAN"}
    >
      <MousePointer />
    </IconButton>
    <IconButton
      tooltipContent={rectangleTool.name}
      on:click={() => selectTool(rectangleTool)}
      selected={selectedTool?.type === "RECTANGLE" && !selectedTool.isSmart}
    >
      <Square />
    </IconButton>
    <IconButton
      tooltipContent={polygonTool.name}
      on:click={() => selectTool(polygonTool)}
      selected={selectedTool?.type === "POLYGON"}
    >
      <Share2 />
    </IconButton>
    <!-- <IconButton tooltipContent="TODO">
      uncomment when ready
      <BrushIcon />
    </IconButton> -->
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
        selected={selectedTool?.type === "POINT_SELECTION" && !!selectedTool.label}
      >
        <PlusCircleIcon />
        <MagicIcon />
      </IconButton>
      <IconButton
        tooltipContent={removeSmartPointTool.name}
        on:click={() => selectTool(removeSmartPointTool)}
        selected={selectedTool?.type === "POINT_SELECTION" && !selectedTool.label}
      >
        <MinusCircleIcon />
        <MagicIcon />
      </IconButton>
      <IconButton
        tooltipContent={smartRectangleTool.name}
        on:click={() => selectTool(smartRectangleTool)}
        selected={selectedTool?.type === "RECTANGLE" && selectedTool.isSmart}
      >
        <Square />
        <MagicIcon />
      </IconButton>
    {/if}
  </div>
</div>
