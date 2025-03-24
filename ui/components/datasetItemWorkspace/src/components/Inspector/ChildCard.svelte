<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Eye, EyeOff, Link, Pencil, Trash2 } from "lucide-svelte";

  import { ToolType } from "@pixano/canvas2d/src/tools";
  import { Annotation, Button, Entity, IconButton, type DisplayControl } from "@pixano/core";

  import { deleteObject, relink } from "../../lib/api/objectsApi";
  import { selectedTool } from "../../lib/stores/datasetItemWorkspaceStores";
  import RelinkAnnotation from "../SaveShape/RelinkAnnotation.svelte";

  export let entity: Entity;
  export let child: Annotation;
  export let handleSetDisplayControl: (
    displayControlProperty: keyof DisplayControl,
    new_value: boolean,
    child: Annotation | null,
  ) => void;
  export let onEditIconClick: (child: Annotation | null) => void;

  let showRelink = false;
  let selectedEntityId: string = "new";

  const handleRelink = () => {
    relink(child, entity, selectedEntityId);
    showRelink = false;
  };
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
    <IconButton
      tooltipContent="Re-link object"
      selected={showRelink}
      on:click={() => {
        showRelink = true;
      }}
    >
      <Link class="h-4" />
    </IconButton>
    <IconButton
      tooltipContent="Delete object"
      redconfirm
      on:click={() => deleteObject(entity, child)}
    >
      <Trash2 class="h-4" />
    </IconButton>
  </div>
</div>
{#if showRelink}
  <div class="flex flex-row gap-4 items-center mr-4">
    <RelinkAnnotation
      bind:selectedEntityId
      baseSchema={child.table_info.base_schema}
      viewRef={child.data.view_ref}
    />
    <Button class="text-white mt-4" on:click={handleRelink}>OK</Button>
  </div>
{/if}
