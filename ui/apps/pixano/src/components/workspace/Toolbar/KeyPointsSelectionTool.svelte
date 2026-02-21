<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  import { ToolType, keyPointTool, type SelectionTool } from "$lib/tools";
  import { IconButton, cn } from "$lib/ui";
  import type { KeypointVertexMetadata } from "$lib/types/geometry";
  import { keypointsIcon } from "$lib/assets";

  import { templates } from "$lib/utils/keyPointsTemplates";
  import {
    newShape,
    selectedKeypointsTemplate,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";

  interface Props {
    selectTool: (tool: SelectionTool) => void;
  }

  let { selectTool }: Props = $props();

  function defineDotColor(metadata: KeypointVertexMetadata, selected: boolean): string | undefined {
    if (metadata.color) {
      return metadata.color;
    }
    if (selected) {
      return "white";
    }
    return undefined;
  }

  function onTemplateClick(templateId: string): void {
    selectedKeypointsTemplate.value = templateId;
    newShape.value = { status: "none" };
  }

  $effect(() => {
    const tool = selectedTool.value;
    if (tool?.type !== ToolType.Keypoint) {
      selectedKeypointsTemplate.value = null;
    } else {
      selectedKeypointsTemplate.value = templates[0].template_id;
    }
  });
</script>

<div
  class={cn(
    "flex items-center gap-1 transition-all duration-300 p-0.5 rounded-xl border border-transparent",
    {
      "bg-muted/40 border-border/20 shadow-inner": selectedTool.value?.type === ToolType.Keypoint,
    },
  )}
>
  <IconButton
    tooltipContent={keyPointTool.name}
    onclick={() => selectTool(keyPointTool)}
    class={cn(
      "h-8 w-8 transition-all duration-300 hover:bg-accent/60",
      selectedTool.value?.type === ToolType.Keypoint ? "text-primary" : "text-foreground",
    )}
  >
    <img src={keypointsIcon} alt="keypoints icon" class="h-4.5 w-4.5" />
  </IconButton>
  {#if selectedTool.value?.type === ToolType.Keypoint}
    <div
      class="flex items-center gap-0.5 animate-in fade-in slide-in-from-left-1 duration-500 bg-background/60 backdrop-blur-sm rounded-lg p-0.5 border border-border/40 shadow-sm ml-0.5"
    >
      {#each templates as template}
        <IconButton
          tooltipContent={template.template_id}
          onclick={() => onTemplateClick(template.template_id)}
          selected={selectedKeypointsTemplate.value === template.template_id}
          class="h-8 w-8"
        >
          {#each template.graph.vertices as vertex, i}
            <div
              class="w-1 h-1 bg-primary rounded-full absolute"
              style={`top: ${vertex.y * 100}%; left: ${vertex.x * 100}%; background: ${defineDotColor(template.vertexMetadata[i], template.template_id === selectedKeypointsTemplate.value)}`}
></div>
          {/each}
        </IconButton>
      {/each}
    </div>
  {/if}
</div>
