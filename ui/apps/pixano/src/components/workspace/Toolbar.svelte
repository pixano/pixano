<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    Cursor,
    Eraser,
    Graph,
    PaintBrush,
    PaintBucket,
    PencilSimple,
    Square,
  } from "phosphor-svelte";

  import BrushSettings from "./Toolbar/BrushSettings.svelte";
  import { polygonIcon } from "$lib/assets";
  import { selectedTool } from "$lib/stores/workspaceStores.svelte";
  import {
    brushDrawTool,
    brushEraseTool,
    panTool,
    polygonTool,
    rectangleTool,
    ToolType,
    type PolygonOutputMode,
  } from "$lib/tools";
  import { cn, IconButton } from "$lib/ui";

  const selectPanTool = () => {
    if (selectedTool.value !== panTool) {
      selectedTool.value = panTool;
    }
  };

  const selectRectangleTool = () => {
    if (selectedTool.value !== rectangleTool) {
      selectedTool.value = rectangleTool;
    }
  };

  const selectBrushTool = () => {
    if (selectedTool.value?.type !== ToolType.Brush) {
      selectedTool.value = brushDrawTool;
    }
  };

  const selectPolygonTool = () => {
    if (selectedTool.value?.type !== ToolType.Polygon) {
      selectedTool.value = polygonTool;
    }
  };

  const setPolygonOutputMode = (outputMode: PolygonOutputMode) => {
    if (selectedTool.value?.type !== ToolType.Polygon) return;
    const polygonSelection = selectedTool.value;
    if (polygonSelection.outputMode !== outputMode) {
      selectedTool.value = {
        ...polygonSelection,
        outputMode,
      };
    }
  };

  // Initialize tool to Pan when Toolbar mounts
  selectedTool.value = panTool;

  let showBrushTools = $derived(selectedTool.value?.type === ToolType.Brush);
  let showPolygonTools = $derived(selectedTool.value?.type === ToolType.Polygon);
</script>

<div
  class="flex items-center gap-1.5 z-10 bg-card/90 backdrop-blur-md p-0.5 px-1.5 rounded-xl border border-border/40 shadow-sm"
>
  <IconButton
    tooltipContent={panTool.name}
    onclick={selectPanTool}
    selected={selectedTool.value?.type === ToolType.Pan}
    class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
  >
    <Cursor weight="regular" class="h-4.5 w-4.5" />
  </IconButton>

  <IconButton
    tooltipContent={rectangleTool.name}
    onclick={selectRectangleTool}
    selected={selectedTool.value?.type === ToolType.Rectangle && !selectedTool.value?.isSmart}
    class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
  >
    <Square class="h-4.5 w-4.5" />
  </IconButton>

  <div
    class={cn(
      "flex items-center gap-1 transition-all duration-300 p-0.5 rounded-xl border border-transparent",
      {
        "bg-muted/40 border-border/20 shadow-inner": showPolygonTools,
      },
    )}
  >
    <IconButton
      tooltipContent="Polygon Tool (P)"
      onclick={selectPolygonTool}
      selected={selectedTool.value?.type === ToolType.Polygon}
      class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
    >
      <img src={polygonIcon} alt="polygon icon" class="h-4.5 w-4.5" />
    </IconButton>

    {#if showPolygonTools}
      <div
        class="flex items-center gap-0.5 animate-in fade-in slide-in-from-left-1 duration-300 bg-background/60 backdrop-blur-sm rounded-lg p-0.5 border border-border/40 shadow-sm"
      >
        <IconButton
          tooltipContent="Keep Raw Polygon Geometry"
          selected={selectedTool.value?.type === ToolType.Polygon &&
            selectedTool.value.outputMode === "polygon"}
          onclick={() => setPolygonOutputMode("polygon")}
          class="h-8 w-8"
        >
          <Graph weight="regular" class="h-4.5 w-4.5" />
        </IconButton>
        <IconButton
          tooltipContent="Convert Polygon To Mask"
          selected={selectedTool.value?.type === ToolType.Polygon &&
            selectedTool.value.outputMode === "mask"}
          onclick={() => setPolygonOutputMode("mask")}
          class="h-8 w-8"
        >
          <PaintBucket class="h-4.5 w-4.5" />
        </IconButton>
      </div>
    {/if}
  </div>

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
      onclick={selectBrushTool}
      selected={selectedTool.value?.type === ToolType.Brush}
      class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
    >
      <PaintBrush weight="regular" class="h-4.5 w-4.5" />
    </IconButton>

    {#if showBrushTools}
      <div
        class="flex items-center gap-0.5 animate-in fade-in slide-in-from-left-1 duration-300 bg-background/60 backdrop-blur-sm rounded-lg p-0.5 border border-border/40 shadow-sm"
      >
        <IconButton
          tooltipContent="Pencil (X to toggle)"
          onclick={() => (selectedTool.value = brushDrawTool)}
          selected={selectedTool.value?.type === ToolType.Brush &&
            selectedTool.value.mode === "draw"}
          class="h-8 w-8"
        >
          <PencilSimple weight="regular" class="h-4.5 w-4.5" />
        </IconButton>
        <IconButton
          tooltipContent="Eraser (X to toggle)"
          onclick={() => (selectedTool.value = brushEraseTool)}
          selected={selectedTool.value?.type === ToolType.Brush &&
            selectedTool.value.mode === "erase"}
          class="h-8 w-8"
        >
          <Eraser class="h-4.5 w-4.5" />
        </IconButton>

        <div class="w-px h-3 bg-border/20 mx-0.5"></div>
        <BrushSettings />
      </div>
    {/if}
  </div>
</div>
