<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import {
    Eye,
    EyeOff,
    Link,
    Minus,
    Pencil,
    Share2,
    Square,
    TangentIcon,
    Trash2,
    Type,
  } from "lucide-svelte";

  import { ToolType } from "@pixano/canvas2d/src/tools";
  import {
    Annotation,
    BaseSchema,
    Button,
    Entity,
    IconButton,
    type DisplayControl,
  } from "@pixano/core";

  import { deleteObject, relink } from "../../lib/api/objectsApi";
  import { mediaViews, selectedTool } from "../../lib/stores/datasetItemWorkspaceStores";
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

  const isMulitView = Object.keys($mediaViews).length > 1;
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
    <IconButton
      disabled
      tooltipContent={child.table_info.base_schema + (isMulitView ? " (" + child.id + ")" : "")}
    >
      {#if child.is_type(BaseSchema.BBox)}
        <Square class="h-4" />
      {/if}
      {#if child.is_type(BaseSchema.Mask)}
        <Share2 class="h-4" />
      {/if}
      {#if child.is_type(BaseSchema.Keypoints)}
        <TangentIcon class="h-4" />
      {/if}
      {#if child.is_type(BaseSchema.Tracklet)}
        <Minus class="h-4" />
      {/if}
      {#if child.is_type(BaseSchema.TextSpan)}
        <Type class="h-4" />
      {/if}
    </IconButton>
    <span
      class="flex-auto block w-full truncate italic"
      title={isMulitView ? child.data.view_ref.name : child.id}
    >
      {isMulitView ? child.data.view_ref.name : child.id}
    </span>
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
        showRelink = !showRelink;
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
      tracklet={child}
    />
    <Button class="text-white mt-4" on:click={handleRelink}>OK</Button>
  </div>
{/if}
