<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Eye, EyeOff, Pencil, Trash2 } from "lucide-svelte";

  import { ToolType } from "@pixano/canvas2d/src/tools";
  import { Annotation, IconButton, type DisplayControl } from "@pixano/core";

  import { selectedTool } from "../../lib/stores/datasetItemWorkspaceStores";

  export let child: Annotation;
  export let handleSetDisplayControl: (
    displayControlProperty: keyof DisplayControl,
    new_value: boolean,
    child: Annotation | null,
  ) => void;
  export let onEditIconClick: (child: Annotation | null) => void;
  export let deleteObject: (child: Annotation | null) => void;
</script>

<div class="flex justify-between border-2 bg-transparent border-transparent">
  <div class="flex-[1_1_auto] flex items-center overflow-hidden min-w-0">
    <IconButton
      on:click={() => handleSetDisplayControl("hidden", !child.ui.displayControl.hidden, child)}
      tooltipContent={!child.ui.displayControl.hidden ? "Hide" : "Show"}
    >
      {#if !child.ui.displayControl.hidden}
        <Eye class="h-4" />
      {:else}
        <EyeOff class="h-4" />
      {/if}
    </IconButton>
    <span class="flex-auto">{child.table_info.base_schema}</span>
  </div>
  <div class="flex-shrink-0 flex items-center justify-end">
    {#if $selectedTool.type !== ToolType.Fusion}
      <IconButton
        tooltipContent="Edit object"
        selected={child.ui.displayControl.editing}
        on:click={() => onEditIconClick(child)}
      >
        <Pencil class="h-4" />
      </IconButton>
    {/if}
    <IconButton tooltipContent="Delete object" redconfirm on:click={() => deleteObject(child)}>
      <Trash2 class="h-4" />
    </IconButton>
  </div>
</div>
