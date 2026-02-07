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
    Square,
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
  import keypoints_icon from "@pixano/core/src/assets/lucide_keypoints_icon.svg";
  import polygon_icon from "@pixano/core/src/assets/lucide_polygon_icon.svg";

  import { deleteObject, onDeleteItemClick, relink } from "../../lib/api/objectsApi";
  import {
    annotations,
    current_itemBBoxes,
    current_itemKeypoints,
    current_itemMasks,
    interpolate,
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
  let currentTrackletChilds: { trackletChild: Annotation; interpolated: boolean }[] = [];

  let childEditing = false;
  let childVisible = true;
  $: if ($annotations) childEditing = child.ui.displayControl.editing;
  $: if ($annotations) childVisible = !child.ui.displayControl.hidden;
  $: if ($annotations || child || $interpolate) buildCurrentTrackletChildList();

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
            interpolated: false,
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
            interpolated: true,
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

<div
  class="flex justify-between items-center py-1 px-1 rounded-lg hover:bg-background hover:shadow-sm border border-transparent hover:border-border/50 transition-all duration-200 group/child"
>
  <div class="flex-[1_1_auto] flex items-center overflow-hidden min-w-0 gap-0.5">
    <IconButton
      on:click={() => handleSetDisplayControl("hidden", childVisible, child)}
      tooltipContent={childVisible ? "Hide" : "Show"}
      class="opacity-60 hover:opacity-100"
    >
      {#if childVisible}
        <Eye class="h-3.5 w-3.5" />
      {:else}
        <EyeOff class="h-3.5 w-3.5" />
      {/if}
    </IconButton>
    <div class="flex items-center text-muted-foreground/60">
      {#if child.is_type(BaseSchema.BBox)}
        <Square class="h-3.5 w-3.5 mx-1" />
      {:else if child.is_type(BaseSchema.Mask)}
        <img src={polygon_icon} alt="polygon icon" class="h-3.5 w-3.5 mx-1 opacity-60" />
      {:else if child.is_type(BaseSchema.Keypoints)}
        <img src={keypoints_icon} alt="keypoints icon" class="h-3.5 w-3.5 mx-1 opacity-60" />
      {:else if child.is_type(BaseSchema.Tracklet)}
        <GitCommitHorizontal class="h-3.5 w-3.5 mx-1" />
      {:else if child.is_type(BaseSchema.TextSpan)}
        <Type class="h-3.5 w-3.5 mx-1" />
      {/if}
    </div>
    <span class="flex-auto block truncate text-[12px] font-medium text-foreground/80" title={child.id}>
      {isMultiView ? child.data.view_ref.name : child.id}
    </span>
  </div>
  <div
    class="flex-shrink-0 flex items-center justify-end gap-0.5 opacity-0 group-hover/child:opacity-100 transition-opacity duration-200"
  >
    {#if $selectedTool.type !== ToolType.Fusion}
      {#if !(child.is_type(BaseSchema.TextSpan) || child.is_type(BaseSchema.Tracklet))}
        <IconButton
          tooltipContent="Edit object"
          selected={childEditing}
          on:click={() => onEditIconClick(child)}
          class="h-7 w-7"
        >
          <Pencil class="h-3.5 w-3.5" />
        </IconButton>
      {/if}
      <IconButton
        tooltipContent="Relink object"
        selected={showRelink}
        on:click={() => {
          showRelink = !showRelink;
        }}
        class="h-7 w-7"
      >
        <Link class="h-3.5 w-3.5" />
      </IconButton>
      <IconButton
        tooltipContent="Delete object"
        redconfirm
        on:click={() => deleteObject(entity, child)}
        class="h-7 w-7 text-muted-foreground hover:text-destructive"
      >
        <Trash2 class="h-3.5 w-3.5" />
      </IconButton>
    {/if}
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
    <Button class="text-primary-foreground mt-4" on:click={handleRelink}>OK</Button>
  </div>
{/if}
{#if child.is_type(BaseSchema.Tracklet)}
  <!-- NOTE: trackletChild may be a clone (from interpolation), not a real Annotation, so we can't use is_type -->
  {#each currentTrackletChilds as { trackletChild, interpolated }}
    {@const displayName = interpolated
      ? `<i>interpolated</i> (${trackletChild.id})`
      : trackletChild.id}
    <div class="flex items-center justify-between w-full overflow-hidden pl-6 py-0.5">
      <div class="flex items-center flex-1 min-w-0 overflow-hidden">
        <IconButton disabled tooltipContent={trackletChild.table_info.base_schema}>
          {#if trackletChild.table_info.base_schema === BaseSchema.BBox}
            <Square class="h-4" />
          {/if}
          {#if trackletChild.table_info.base_schema === BaseSchema.Mask}
            <img src={polygon_icon} alt="polygon icon" class="h-4" />
          {/if}
          {#if trackletChild.table_info.base_schema === BaseSchema.Keypoints}
            <img src={keypoints_icon} alt="keypoints icon" class="h-4" />
          {/if}
          {#if trackletChild.table_info.base_schema === BaseSchema.TextSpan}
            <Type class="h-4" />
          {/if}
        </IconButton>

        <span class="block w-full truncate ml-2" title={trackletChild.id}>
          {@html displayName}
        </span>
      </div>
      {#if $selectedTool.type !== ToolType.Fusion && !interpolated}
        <div class="flex items-center mr-4">
          {#if [BaseSchema.BBox, BaseSchema.Mask, BaseSchema.Keypoints].includes(trackletChild.table_info.base_schema)}
            <IconButton
              tooltipContent="Edit object"
              selected={trackletChild.ui.displayControl.editing}
              on:click={() => onEditIconClick(trackletChild)}
            >
              <Pencil class="h-4" />
            </IconButton>
          {/if}
          <IconButton
            tooltipContent="Delete object"
            redconfirm
            on:click={() => onDeleteItemClick(child, trackletChild.ui.frame_index, trackletChild)}
          >
            <Trash2 class="h-4" />
          </IconButton>
        </div>
      {/if}
    </div>
  {/each}
{/if}
