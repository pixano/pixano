<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { TangentIcon } from "lucide-svelte";

  import { cn, IconButton, type Vertex } from "@pixano/core/src";

  import { keyPointTool } from "../../lib/settings/selectionTools";
  import {
    selectedTool,
    selectedKeypointsTemplate,
    newShape,
  } from "../../lib/stores/datasetItemWorkspaceStores";

  import { templates } from "../../lib/settings/keyPointsTemplates";

  const defineDotColor = (vertex: Vertex, selected: boolean) => {
    if (vertex.features?.color) return vertex.features.color;
    if (selected) return "white";
  };

  const onTemplateClick = (templateId: string) => {
    selectedKeypointsTemplate.set(templateId);
    newShape.set({ status: "none" });
  };

  selectedTool.subscribe((tool) => {
    if (tool?.type !== "KEY_POINT") {
      selectedKeypointsTemplate.set(null);
    } else {
      selectedKeypointsTemplate.set(templates[0].template_id);
    }
  });
</script>

<div
  class={cn("flex items-center flex-col gap-4 mt-4", {
    "bg-slate-200 rounded-sm": $selectedTool?.type === "KEY_POINT",
  })}
>
  <IconButton tooltipContent={keyPointTool.name} on:click={() => selectedTool.set(keyPointTool)}>
    <TangentIcon />
  </IconButton>
  {#if $selectedTool?.type === "KEY_POINT"}
    {#each templates as template}
      <IconButton
        tooltipContent={template.template_id}
        on:click={() => onTemplateClick(template.template_id)}
        selected={$selectedKeypointsTemplate === template.template_id}
      >
        {#each template.vertices as vertex}
          <div
            class="w-1 h-1 bg-primary rounded-full absolute"
            style={`top: ${vertex.y * 100}%; left: ${vertex.x * 100}%; background: ${defineDotColor(vertex, template.template_id === $selectedKeypointsTemplate)}`}
          />
        {/each}
      </IconButton>
    {/each}
  {/if}
</div>
