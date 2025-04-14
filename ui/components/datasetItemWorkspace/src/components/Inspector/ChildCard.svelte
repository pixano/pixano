<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  /* eslint-disable svelte/no-at-html-tags */
  // Imports
  import {
    Eye,
    EyeOff,
    GitCommitHorizontal,
    Link,
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
    BBox,
    Button,
    Entity,
    IconButton,
    Mask,
    Tracklet,
    type DisplayControl,
    type KeypointsTemplate,
  } from "@pixano/core";

  import { deleteObject, relink } from "../../lib/api/objectsApi";
  import {
    annotations,
    current_itemBBoxes,
    current_itemKeypoints,
    current_itemMasks,
    mediaViews,
    selectedTool,
  } from "../../lib/stores/datasetItemWorkspaceStores";
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
  let mustMerge: boolean = false;
  let overlapTargetId: string = "";
  let currentTrackletChilds: { trackletChild: Annotation; displayName: string }[] = [];

  $: if ($annotations || child) buildCurrentTrackletChildList();

  const buildCurrentTrackletChildList = () => {
    if (child.is_type(BaseSchema.Tracklet)) {
      currentTrackletChilds = [];
      const trackletChilds = (child as Tracklet).ui.childs;
      const current_Anns = [
        ...$current_itemBBoxes,
        ...$current_itemKeypoints,
        ...$current_itemMasks,
      ] as (BBox | KeypointsTemplate | Mask)[];

      current_Anns.forEach((cann) => {
        const directMatch = trackletChilds.find((ann) => ann.id === cann.id);

        if (directMatch) {
          currentTrackletChilds.push({
            trackletChild: directMatch,
            displayName: cann.id,
          });
        } else if (
          trackletChilds.some(
            (ann) =>
              cann.ui &&
              "startRef" in cann.ui &&
              cann.ui.startRef &&
              ann.id === cann.ui.startRef.id,
          )
        ) {
          currentTrackletChilds.push({
            trackletChild: cann as Annotation,
            displayName: `<i>interpolated</i> (${cann.id})`,
          });
        }
      });
    }
  };

  const isMultiView = Object.keys($mediaViews).length > 1;
  const handleRelink = () => {
    relink(child, entity, selectedEntityId, mustMerge, overlapTargetId);
    showRelink = false;
  };
</script>

<div class="flex justify-between bg-transparent border-transparent">
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
    <IconButton disabled tooltipContent={child.table_info.base_schema}>
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
        <GitCommitHorizontal class="h-4" />
      {/if}
      {#if child.is_type(BaseSchema.TextSpan)}
        <Type class="h-4" />
      {/if}
    </IconButton>
    <span class="flex-auto block w-full truncate" title={child.id}>
      {isMultiView ? child.data.view_ref.name : child.id}
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
      <IconButton
        tooltipContent="Relink object"
        selected={showRelink}
        on:click={() => {
          showRelink = !showRelink;
        }}
      >
        <Link class="h-4" />
      </IconButton>
    {/if}
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
      bind:mustMerge
      bind:overlapTargetId
      baseSchema={child.table_info.base_schema}
      viewRef={child.data.view_ref}
      tracklet={child}
    />
    <Button class="text-white mt-4" on:click={handleRelink}>OK</Button>
  </div>
{/if}
{#if child.is_type(BaseSchema.Tracklet)}
  {#each currentTrackletChilds as { trackletChild, displayName }}
    <div class="flex-[1_1_auto] flex items-center overflow-hidden min-w-0 ml-4">
      <IconButton disabled tooltipContent={trackletChild.table_info.base_schema}>
        <!-- trackletChild may be a clone (from interpolation), not a real Annotation, so we can't use is_type -->
        {#if trackletChild.table_info.base_schema === BaseSchema.BBox}
          <Square class="h-4" />
        {/if}
        {#if trackletChild.table_info.base_schema === BaseSchema.Mask}
          <Share2 class="h-4" />
        {/if}
        {#if trackletChild.table_info.base_schema === BaseSchema.Keypoints}
          <TangentIcon class="h-4" />
        {/if}
        {#if trackletChild.table_info.base_schema === BaseSchema.TextSpan}
          <Type class="h-4" />
        {/if}
      </IconButton>
      <span class="flex-auto block w-full truncate" title={trackletChild.id}>
        {@html displayName}
      </span>
    </div>
  {/each}
{/if}
