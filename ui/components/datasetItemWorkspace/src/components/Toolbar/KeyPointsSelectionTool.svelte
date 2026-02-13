<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onDestroy } from "svelte";

  import { ToolType } from "@pixano/canvas2d/src/tools";
  import { cn, IconButton, type SelectionTool, type Vertex } from "@pixano/core/src";
  import keypoints_icon from "@pixano/core/src/assets/lucide_keypoints_icon.svg";

  import { templates } from "../../lib/settings/keyPointsTemplates";
  import { keyPointTool } from "../../lib/settings/selectionTools";
  import {
    newShape,
    selectedKeypointsTemplate,
    selectedTool,
  } from "../../lib/stores/datasetItemWorkspaceStores";

  export let selectTool: (tool: SelectionTool) => void;

  const defineDotColor = (vertex: Vertex, selected: boolean) => {
    if (vertex.features?.color) return vertex.features.color;
    if (selected) return "white";
  };

  const onTemplateClick = (templateId: string) => {
    selectedKeypointsTemplate.set(templateId);
    newShape.set({ status: "none" });
  };

  const unsubscribeSelectedTool = selectedTool.subscribe((tool) => {
    if (tool?.type !== ToolType.Keypoint) {
      selectedKeypointsTemplate.set(null);
    } else {
      selectedKeypointsTemplate.set(templates[0].template_id);
    }
  });

  onDestroy(unsubscribeSelectedTool);
</script>

<div
  class={cn(
    "flex items-center gap-1 transition-all duration-300 p-0.5 rounded-xl border border-transparent",
    {
      "bg-muted/40 border-border/20 shadow-inner": $selectedTool?.type === ToolType.Keypoint,
    },
  )}
>
  <IconButton
    tooltipContent={keyPointTool.name}
    on:click={() => selectTool(keyPointTool)}
    class={cn(
      "h-8 w-8 transition-all duration-300 hover:bg-accent/60",
      $selectedTool?.type === ToolType.Keypoint ? "text-primary" : "text-foreground",
    )}
  >
    <img src={keypoints_icon} alt="keypoints icon" class="h-4.5 w-4.5" />
  </IconButton>
  {#if $selectedTool?.type === ToolType.Keypoint}
    <div
      class="flex items-center gap-0.5 animate-in fade-in slide-in-from-left-1 duration-500 bg-background/60 backdrop-blur-sm rounded-lg p-0.5 border border-border/40 shadow-sm ml-0.5"
    >
      {#each templates as template}
        <IconButton
          tooltipContent={template.template_id}
          on:click={() => onTemplateClick(template.template_id)}
          selected={$selectedKeypointsTemplate === template.template_id}
          class="h-8 w-8"
        >
          {#each template.vertices as vertex}
            <div
              class="w-1 h-1 bg-primary rounded-full absolute"
              style={`top: ${vertex.y * 100}%; left: ${vertex.x * 100}%; background: ${defineDotColor(vertex, template.template_id === $selectedKeypointsTemplate)}`}
            />
          {/each}
        </IconButton>
      {/each}
    </div>
  {/if}
</div>
