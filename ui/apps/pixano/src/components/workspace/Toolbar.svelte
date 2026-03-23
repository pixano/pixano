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
    LineSegments,
    MagicWand,
    PaintBrush,
    PaintBucket,
    PencilSimple,
    Square,
  } from "phosphor-svelte";

  import BrushSettings from "./Toolbar/BrushSettings.svelte";
  import { polygonIcon } from "$lib/assets";
  import { ensureInferenceRegistryLoaded } from "$lib/services/inferenceService.svelte";
  import {
    currentSegmentationModels,
    inferenceServerStore,
    selectedStaticSegmentationModel,
    selectedVideoSegmentationModel,
  } from "$lib/stores/inferenceStores.svelte";
  import {
    itemMetas,
    selectedTool,
    smartSegmentationUiState,
  } from "$lib/stores/workspaceStores.svelte";
  import {
    brushDrawTool,
    brushEraseTool,
    interactiveSegmenterTool,
    panTool,
    polygonTool,
    polylineTool,
    rectangleTool,
    ToolType,
    vosTool,
    type PolygonOutputMode,
  } from "$lib/tools";
  import { WorkspaceType } from "$lib/types/dataset";
  import { getInferenceModelKey } from "$lib/types/inference";
  import { cn, IconButton, ModelSelectBadge } from "$lib/ui";

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

  const selectInteractiveSegmenterTool = () => {
    if (
      selectedTool.value?.type !== ToolType.InteractiveSegmenter &&
      selectedTool.value?.type !== ToolType.VOS
    ) {
      if (itemMetas.value?.type === WorkspaceType.VIDEO) {
        selectedTool.value = vosTool;
      } else {
        selectedTool.value = interactiveSegmenterTool;
      }
    }
  };

  const setSegmentationModelSelection = (modelKey: string) => {
    const selectedModel =
      currentSegmentationModels.value.find((model) => getInferenceModelKey(model) === modelKey) ??
      null;
    const selection = selectedModel
      ? {
          name: selectedModel.name,
          provider_name: selectedModel.provider_name,
        }
      : null;

    if (itemMetas.value?.type === WorkspaceType.VIDEO) {
      selectedVideoSegmentationModel.value = selection;
      return;
    }

    selectedStaticSegmentationModel.value = selection;
  };

  const setInteractivePromptMode = (
    promptMode: (typeof interactiveSegmenterTool)["promptMode"],
  ) => {
    if (
      selectedTool.value?.type !== ToolType.InteractiveSegmenter &&
      selectedTool.value?.type !== ToolType.VOS
    ) {
      if (itemMetas.value?.type === WorkspaceType.VIDEO) {
        selectedTool.value = { ...vosTool, promptMode };
      } else {
        selectedTool.value = { ...interactiveSegmenterTool, promptMode };
      }
      return;
    }

    if (selectedTool.value.promptMode !== promptMode) {
      selectedTool.value = {
        ...selectedTool.value,
        promptMode,
      };
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

  const selectPolylineTool = () => {
    if (selectedTool.value?.type !== ToolType.Polyline) {
      selectedTool.value = polylineTool;
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
  let showInteractiveSegmenterTools = $derived(
    selectedTool.value?.type === ToolType.InteractiveSegmenter ||
      selectedTool.value?.type === ToolType.VOS,
  );
  let showPolygonTools = $derived(selectedTool.value?.type === ToolType.Polygon);
  let smartInferencePending = $derived(smartSegmentationUiState.value.phase === "pending");
  let currentWorkspaceType = $derived(itemMetas.value?.type ?? WorkspaceType.IMAGE);
  let compatibleSegmentationModels = $derived(currentSegmentationModels.value);
  let currentSegmentationSelection = $derived(
    currentWorkspaceType === WorkspaceType.VIDEO
      ? selectedVideoSegmentationModel.value
      : selectedStaticSegmentationModel.value,
  );
  let currentSegmentationModelKey = $derived(
    currentSegmentationSelection ? getInferenceModelKey(currentSegmentationSelection) : "",
  );
  let segmentationModelLabel = $derived.by(() => {
    if (currentSegmentationSelection) {
      return currentSegmentationSelection.name;
    }
    if (inferenceServerStore.value.status === "loading") {
      return "Loading";
    }
    if (!inferenceServerStore.value.connected) {
      return "No server";
    }
    return currentWorkspaceType === WorkspaceType.VIDEO ? "No tracking model" : "No image model";
  });
  let segmentationSelectorDisabled = $derived(
    smartInferencePending ||
      compatibleSegmentationModels.length === 0 ||
      inferenceServerStore.value.status === "loading",
  );
  $effect(() => {
    void ensureInferenceRegistryLoaded();
  });
</script>

<div
  class="flex items-center gap-1.5 z-10 bg-card/90 backdrop-blur-md p-0.5 px-1.5 rounded-xl border border-border/40 shadow-sm"
  aria-busy={smartInferencePending}
>
  <IconButton
    tooltipContent={panTool.name}
    onclick={selectPanTool}
    selected={selectedTool.value?.type === ToolType.Pan}
    disabled={smartInferencePending}
    class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
  >
    <Cursor weight="regular" class="h-4.5 w-4.5" />
  </IconButton>

  <IconButton
    tooltipContent={rectangleTool.name}
    onclick={selectRectangleTool}
    selected={selectedTool.value?.type === ToolType.Rectangle && !selectedTool.value?.isSmart}
    disabled={smartInferencePending}
    class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
  >
    <Square class="h-4.5 w-4.5" />
  </IconButton>

  <div
    class={cn(
      "flex items-center gap-1 transition-all duration-300 p-0.5 rounded-xl border border-transparent",
      {
        "bg-muted/40 border-border/20 shadow-inner": showInteractiveSegmenterTools,
      },
    )}
  >
    <IconButton
      tooltipContent="Interactive Smart Segmentation (W)"
      onclick={selectInteractiveSegmenterTool}
      selected={selectedTool.value?.type === ToolType.InteractiveSegmenter ||
        selectedTool.value?.type === ToolType.VOS}
      disabled={smartInferencePending}
      class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
    >
      <MagicWand weight="regular" class="h-4.5 w-4.5" />
    </IconButton>

    {#if showInteractiveSegmenterTools}
      <div
        class="flex items-center gap-0.5 animate-in fade-in slide-in-from-left-1 duration-300 bg-background/60 backdrop-blur-sm rounded-lg p-0.5 border border-border/40 shadow-sm"
      >
        <IconButton
          tooltipContent="Positive Point Prompt (X toggles +/-)"
          onclick={() => setInteractivePromptMode("positive")}
          selected={(selectedTool.value?.type === ToolType.InteractiveSegmenter ||
            selectedTool.value?.type === ToolType.VOS) &&
            selectedTool.value.promptMode === "positive"}
          disabled={smartInferencePending}
          class="h-8 w-8"
        >
          <span class="text-base font-semibold leading-none">+</span>
        </IconButton>
        <IconButton
          tooltipContent="Negative Point Prompt (X toggles +/-)"
          onclick={() => setInteractivePromptMode("negative")}
          selected={(selectedTool.value?.type === ToolType.InteractiveSegmenter ||
            selectedTool.value?.type === ToolType.VOS) &&
            selectedTool.value.promptMode === "negative"}
          disabled={smartInferencePending}
          class="h-8 w-8"
        >
          <span class="text-base font-semibold leading-none">-</span>
        </IconButton>
        <IconButton
          tooltipContent="Bounding Box Prompt (R)"
          onclick={() => setInteractivePromptMode("box")}
          selected={(selectedTool.value?.type === ToolType.InteractiveSegmenter ||
            selectedTool.value?.type === ToolType.VOS) &&
            selectedTool.value.promptMode === "box"}
          disabled={smartInferencePending}
          class="h-8 w-8"
        >
          <Square class="h-4 w-4" />
        </IconButton>

        <div class="mx-1 h-4 w-px bg-border/30"></div>

        <ModelSelectBadge
          models={compatibleSegmentationModels}
          selectedModelKey={currentSegmentationModelKey}
          disabled={segmentationSelectorDisabled}
          label={segmentationModelLabel}
          onValueChange={setSegmentationModelSelection}
        />
      </div>
    {/if}
  </div>

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
      disabled={smartInferencePending}
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
          disabled={smartInferencePending}
          class="h-8 w-8"
        >
          <Graph weight="regular" class="h-4.5 w-4.5" />
        </IconButton>
        <IconButton
          tooltipContent="Convert Polygon To Mask"
          selected={selectedTool.value?.type === ToolType.Polygon &&
            selectedTool.value.outputMode === "mask"}
          onclick={() => setPolygonOutputMode("mask")}
          disabled={smartInferencePending}
          class="h-8 w-8"
        >
          <PaintBucket class="h-4.5 w-4.5" />
        </IconButton>
      </div>
    {/if}
  </div>

  <IconButton
    tooltipContent="Polyline Tool (L)"
    onclick={selectPolylineTool}
    selected={selectedTool.value?.type === ToolType.Polyline}
    disabled={smartInferencePending}
    class="h-8 w-8 hover:bg-accent/60 transition-all duration-200"
  >
    <LineSegments weight="regular" class="h-4.5 w-4.5" />
  </IconButton>

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
      disabled={smartInferencePending}
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
          disabled={smartInferencePending}
          class="h-8 w-8"
        >
          <PencilSimple weight="regular" class="h-4.5 w-4.5" />
        </IconButton>
        <IconButton
          tooltipContent="Eraser (X to toggle)"
          onclick={() => (selectedTool.value = brushEraseTool)}
          selected={selectedTool.value?.type === ToolType.Brush &&
            selectedTool.value.mode === "erase"}
          disabled={smartInferencePending}
          class="h-8 w-8"
        >
          <Eraser class="h-4.5 w-4.5" />
        </IconButton>

        <div class="w-px h-3 bg-border/20 mx-0.5"></div>
        <BrushSettings disabled={smartInferencePending} />
      </div>
    {/if}
  </div>
</div>
