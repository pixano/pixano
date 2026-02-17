<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    Eraser,
    MousePointer2,
    PaintBucket,
    Paintbrush,
    PencilLine,
    Square,
    Waypoints,
  } from "lucide-svelte";
  import { onMount } from "svelte";

  import {
    type PolygonOutputMode,
    ToolType,
    brushDrawTool,
    brushEraseTool,
    panTool,
    polygonTool,
    rectangleTool,
  } from "@pixano/tools";
  import { cn } from "@pixano/core/src";
  import { IconButton } from "@pixano/core/src";
  import polygon_icon from "@pixano/core/src/assets/lucide_polygon_icon.svg";
  import { selectedTool } from "../lib/stores/datasetItemWorkspaceStores";
  import BrushSettings from "./Toolbar/BrushSettings.svelte";

  const selectPanTool = () => {
    if ($selectedTool !== panTool) {
      selectedTool.set(panTool);
    }
  };

  const selectRectangleTool = () => {
    if ($selectedTool !== rectangleTool) {
      selectedTool.set(rectangleTool);
    }
  };

  const selectBrushTool = () => {
    if ($selectedTool?.type !== ToolType.Brush) {
      selectedTool.set(brushDrawTool);
    }
  };

  const selectPolygonTool = () => {
    if ($selectedTool?.type !== ToolType.Polygon) {
      selectedTool.set(polygonTool);
    }
  };

  const setPolygonOutputMode = (outputMode: PolygonOutputMode) => {
    if ($selectedTool?.type !== ToolType.Polygon) return;
    const polygonSelection = $selectedTool;
    if (polygonSelection.outputMode !== outputMode) {
      selectedTool.set({
        ...polygonSelection,
        outputMode,
      });
    }
  };

  onMount(() => {
    selectedTool.set(panTool);
  });

  $: showBrushTools = $selectedTool?.type === ToolType.Brush;
  $: showPolygonTools = $selectedTool?.type === ToolType.Polygon;
</script>

<div
  class="flex items-center gap-1.5 z-10 bg-card/90 backdrop-blur-md p-0.5 px-1.5 rounded-xl border border-border/40 shadow-sm"
>
  <IconButton
    tooltipContent={panTool.name}
    on:click={selectPanTool}
    selected={$selectedTool?.type === ToolType.Pan}
    class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
  >
    <MousePointer2 class="h-4.5 w-4.5" />
  </IconButton>

  <IconButton
    tooltipContent={rectangleTool.name}
    on:click={selectRectangleTool}
    selected={$selectedTool?.type === ToolType.Rectangle && !$selectedTool?.isSmart}
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
      on:click={selectPolygonTool}
      selected={$selectedTool?.type === ToolType.Polygon}
      class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
    >
      <img src={polygon_icon} alt="polygon icon" class="h-4.5 w-4.5" />
    </IconButton>

    {#if showPolygonTools}
      <div
        class="flex items-center gap-0.5 animate-in fade-in slide-in-from-left-1 duration-300 bg-background/60 backdrop-blur-sm rounded-lg p-0.5 border border-border/40 shadow-sm"
      >
        <IconButton
          tooltipContent="Keep Raw Polygon Geometry"
          selected={$selectedTool?.type === ToolType.Polygon && $selectedTool.outputMode === "polygon"}
          on:click={() => setPolygonOutputMode("polygon")}
          class="h-8 w-8"
        >
          <Waypoints class="h-4.5 w-4.5" />
        </IconButton>
        <IconButton
          tooltipContent="Convert Polygon To Mask"
          selected={$selectedTool?.type === ToolType.Polygon && $selectedTool.outputMode === "mask"}
          on:click={() => setPolygonOutputMode("mask")}
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
      on:click={selectBrushTool}
      selected={$selectedTool?.type === ToolType.Brush}
      class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
    >
      <Paintbrush class="h-4.5 w-4.5" />
    </IconButton>

    {#if showBrushTools}
      <div
        class="flex items-center gap-0.5 animate-in fade-in slide-in-from-left-1 duration-300 bg-background/60 backdrop-blur-sm rounded-lg p-0.5 border border-border/40 shadow-sm"
      >
        <IconButton
          tooltipContent="Pencil (X to toggle)"
          on:click={() => selectedTool.set(brushDrawTool)}
          selected={$selectedTool?.type === ToolType.Brush && $selectedTool.mode === "draw"}
          class="h-8 w-8"
        >
          <PencilLine class="h-4.5 w-4.5" />
        </IconButton>
        <IconButton
          tooltipContent="Eraser (X to toggle)"
          on:click={() => selectedTool.set(brushEraseTool)}
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
</div>
