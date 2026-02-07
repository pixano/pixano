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
  class={cn("flex items-center gap-4", {
    "bg-accent rounded-sm": $selectedTool?.type === ToolType.Keypoint,
  })}
>
  <IconButton tooltipContent={keyPointTool.name} on:click={() => selectTool(keyPointTool)}>
    <img src={keypoints_icon} alt="keypoints icon" />
  </IconButton>
  {#if $selectedTool?.type === ToolType.Keypoint}
    {#each templates as template}
      <IconButton
        tooltipContent={template.template_id}
        on:click={() => onTemplateClick(template.template_id)}
        selected={$selectedKeypointsTemplate === template.template_id}
      >
        {#each template.vertices as vertex}
          <div>
            <div
              class="w-1 h-1 bg-primary rounded-full absolute"
              style={`top: ${vertex.y * 100}%; left: ${vertex.x * 100}%; background: ${defineDotColor(vertex, template.template_id === $selectedKeypointsTemplate)}`}
            />
          </div>
        {/each}
      </IconButton>
    {/each}
  {/if}
</div>
