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
  import TooltipIconButton from "@pixano/core/src/lib/components/molecules/TooltipIconButton.svelte";

  import type { SelectionTool } from "@pixano/core";
  import { cn } from "@pixano/core/src/lib/utils";

  import MagicIcon from "../assets/MagicIcon.svelte";
  import {
    panTool,
    smartRectangleTool,
    rectangleTool,
    addSmartPointTool,
    removeSmartPointTool,
  } from "../lib/settings/selectionTools";
  import { interactiveSegmenterModel, newShape } from "../lib/stores/imageWorkspaceStores";

  export let selectedTool: SelectionTool | null;
  let previousSelectedTool: SelectionTool | null = null;
  let showSmartTools: boolean = false;

  const selectTool = (tool: SelectionTool | null) => {
    if (tool !== selectedTool) selectedTool = tool;
  };

  const handleSmartToolClick = () => {
    if (!showSmartTools) {
      selectTool(addSmartPointTool);
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

  $: {
    if (!previousSelectedTool?.isSmart || !selectedTool?.isSmart) {
      newShape.set(null);
    }
    previousSelectedTool = selectedTool;
  }
</script>

<div class="h-full shadow-md bg-popover p-1">
  <div class="border-b border-gray-400 pb-4 flex items-center flex-col gap-4 bg-popover">
    <TooltipIconButton
      tooltipContent="Move your picture around"
      on:click={() => selectTool(panTool)}
      selected={selectedTool?.type === "PAN"}
    >
      <MousePointer />
    </TooltipIconButton>
    <TooltipIconButton
      on:click={() => selectTool(rectangleTool)}
      selected={selectedTool?.type === "RECTANGLE" && !selectedTool.isSmart}
    >
      <Square />
    </TooltipIconButton>
    <TooltipIconButton tooltipContent="TODO">
      <Share2 />
    </TooltipIconButton>
    <TooltipIconButton tooltipContent="TODO">
      <BrushIcon />
    </TooltipIconButton>
  </div>
  <div
    class={cn("flex items-center flex-col gap-4 mt-4", {
      "bg-primary-light rounded-sm": showSmartTools,
    })}
  >
    <TooltipIconButton tooltipContent="Smart tools" on:click={handleSmartToolClick}>
      <BrushIcon />
      <MagicIcon />
    </TooltipIconButton>
    {#if showSmartTools}
      <TooltipIconButton
        tooltipContent={addSmartPointTool.name}
        on:click={() => selectTool(addSmartPointTool)}
        selected={selectedTool?.type === "POINT_SELECTION" && !!selectedTool.label}
      >
        <PlusCircleIcon />
        <MagicIcon />
      </TooltipIconButton>
      <TooltipIconButton
        tooltipContent={removeSmartPointTool.name}
        on:click={() => selectTool(removeSmartPointTool)}
        selected={selectedTool?.type === "POINT_SELECTION" && !selectedTool.label}
      >
        <MinusCircleIcon />
        <MagicIcon />
      </TooltipIconButton>
      <TooltipIconButton
        tooltipContent="Smart rectangle"
        on:click={() => selectTool(smartRectangleTool)}
        selected={selectedTool?.type === "RECTANGLE" && selectedTool.isSmart}
      >
        <Square />
        <MagicIcon />
      </TooltipIconButton>
    {/if}
  </div>
</div>
