<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  
  /* eslint-disable svelte/no-at-html-tags */
  // Imports
  import { Eye, EyeClosed, GitCommit, Link, Pencil, Square, Trash, TextT, Ghost } from "phosphor-svelte";

  import { ToolType } from "$lib/tools";
  import { Button } from "bits-ui";

  import {
    Annotation,
    BaseSchema,
    BBox,
    Entity,
    IconButton,
    Mask,
    Tracklet,
    type DisplayControl,
    type KeypointAnnotation,
  } from "$lib/ui";
  import { cn } from "$lib/utils/styleUtils";
  import { keypointsIcon } from "$lib/assets";

  import { deleteEntity, onDeleteTrackItemClick } from "$lib/utils/entityDeletion";
  import { relink } from "$lib/utils/entityRelink";
  import { getWorkspaceContext } from "$lib/workspace/context";
  import {
    annotations,
    current_itemBBoxes,
    current_itemKeypoints,
    current_itemMasks,
    interpolate,
    mediaViews,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import RelinkAnnotation from "../SaveShape/RelinkAnnotation.svelte";

  interface Props {
    entity: Entity;
    child: Annotation;
    handleSetDisplayControl: (
    displayControlProperty: keyof DisplayControl,
    new_value: boolean,
    child: Annotation | null,
  ) => void;
    onEditIconClick: (child: Annotation | null) => void;
  }

  let {
    entity,
    child,
    handleSetDisplayControl,
    onEditIconClick
  }: Props = $props();

  let showRelink = $state(false);
  let selectedEntityId: string = $state("new");
  let mustMerge: boolean = $state(false);
  let overlapTargetId: string = $state("");
  const { manifest } = getWorkspaceContext();

  const childEditing = $derived.by(() => {
    void annotations.value;
    return child.ui.displayControl.editing;
  });

  const childVisible = $derived.by(() => {
    void annotations.value;
    return !child.ui.displayControl.hidden;
  });

  const currentTrackChilds = $derived.by(() => {
    if (!child.is_type(BaseSchema.Tracklet)) return [];
    void interpolate.value;
    const trackChilds = (child as Tracklet).ui.childs;
    const current_Anns = [
      ...current_itemBBoxes.value,
      ...current_itemKeypoints.value,
      ...current_itemMasks.value,
    ] as (BBox | KeypointAnnotation | Mask)[];

    const result: { trackChild: Annotation; interpolated: boolean }[] = [];
    current_Anns.forEach((cann) => {
      const directMatch = trackChilds.find((ann) => ann.id === cann.id);
      if (directMatch) {
        result.push({ trackChild: directMatch, interpolated: false });
      } else if (
        trackChilds.some(
          (ann) =>
            cann.ui &&
            "startRef" in cann.ui &&
            cann.ui.startRef &&
            ann.id === cann.ui.startRef.id,
        )
      ) {
        result.push({ trackChild: cann as Annotation, interpolated: true });
      }
    });
    return result;
  });

  const isMultiView = Object.keys(mediaViews.value).length > 1;

  const handleRelink = () => {
    relink(child, entity, selectedEntityId, mustMerge, overlapTargetId, manifest);
    showRelink = false;
  };
</script>

<div
  class="flex justify-between items-center py-1 px-1 rounded-lg hover:bg-background hover:shadow-sm border border-transparent hover:border-border/50 transition-all duration-200 group/child"
>
  <div class="flex-[1_1_auto] flex items-center overflow-hidden min-w-0 gap-0.5">
    <IconButton
      onclick={() => handleSetDisplayControl("hidden", childVisible, child)}
      tooltipContent={childVisible ? "Hide" : "Show"}
      class="opacity-60 hover:opacity-100"
    >
      {#if childVisible}
        <Eye class="h-3.5 w-3.5" />
      {:else}
        <EyeClosed weight="regular" class="h-3.5 w-3.5" />
      {/if}
    </IconButton>
    <div class="flex items-center text-muted-foreground/60">
      {#if child.is_type(BaseSchema.BBox)}
        <Square class="h-3.5 w-3.5 mx-1" />
      {:else if child.is_type(BaseSchema.Mask)}
        <Ghost weight="regular" class="h-3.5 w-3.5 mx-1 opacity-60" />
      {:else if child.is_type(BaseSchema.Keypoints)}
        <img src={keypointsIcon} alt="keypoints icon" class="h-3.5 w-3.5 mx-1 opacity-60" />
      {:else if child.is_type(BaseSchema.Tracklet)}
        <GitCommit weight="regular" class="h-3.5 w-3.5 mx-1" />
      {:else if child.is_type(BaseSchema.TextSpan)}
        <TextT weight="regular" class="h-3.5 w-3.5 mx-1" />
      {/if}
    </div>
    <span
      class="flex-auto block truncate text-[12px] font-medium text-foreground/80"
      title={child.id}
    >
      {isMultiView ? child.data.view_name : child.id}
    </span>
  </div>
  <div
    class="flex-shrink-0 flex items-center justify-end gap-0.5 opacity-0 group-hover/child:opacity-100 transition-opacity duration-200"
  >
    {#if selectedTool.value?.type !== ToolType.Fusion}
      {#if !(child.is_type(BaseSchema.TextSpan) || child.is_type(BaseSchema.Tracklet))}
        <IconButton
          tooltipContent="Edit object"
          selected={childEditing}
          onclick={() => onEditIconClick(child)}
          class="h-7 w-7"
        >
          <Pencil class="h-3.5 w-3.5" />
        </IconButton>
      {/if}
      <IconButton
        tooltipContent="Relink object"
        selected={showRelink}
        onclick={() => {
          showRelink = !showRelink;
        }}
        class="h-7 w-7"
      >
        <Link class="h-3.5 w-3.5" />
      </IconButton>
      <IconButton
        tooltipContent="Delete object"
        redconfirm
        onclick={() => deleteEntity(entity, child)}
        class="h-7 w-7 text-muted-foreground hover:text-destructive"
      >
        <Trash weight="regular" class="h-3.5 w-3.5" />
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
      viewRef={{ name: child.data.view_name, id: child.data.frame_id }}
      track={child}
    />
    <Button.Root
      type="button"
      class={cn(
        "inline-flex items-center justify-center rounded-lg text-sm font-medium whitespace-nowrap ring-offset-background transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2 mt-4",
      )}
      onclick={handleRelink}
    >
      OK
    </Button.Root>
  </div>
{/if}
{#if child.is_type(BaseSchema.Tracklet)}
  <!-- NOTE: trackChild may be a clone (from interpolation), not a real Annotation, so we can't use is_type -->
  {#each currentTrackChilds as { trackChild, interpolated }}
    {@const displayName = interpolated
      ? `<i>interpolated</i> (${trackChild.id})`
      : trackChild.id}
    <div class="flex items-center justify-between w-full overflow-hidden pl-6 py-0.5">
      <div class="flex items-center flex-1 min-w-0 overflow-hidden">
        <IconButton disabled tooltipContent={trackChild.table_info.base_schema}>
          {#if trackChild.table_info.base_schema === BaseSchema.BBox}
            <Square class="h-4" />
          {/if}
          {#if trackChild.table_info.base_schema === BaseSchema.Mask}
            <Ghost weight="regular" class="h-4" />
          {/if}
          {#if trackChild.table_info.base_schema === BaseSchema.Keypoints}
            <img src={keypointsIcon} alt="keypoints icon" class="h-4" />
          {/if}
          {#if trackChild.table_info.base_schema === BaseSchema.TextSpan}
            <TextT weight="regular" class="h-4" />
          {/if}
        </IconButton>

        <span class="block w-full truncate ml-2" title={trackChild.id}>
          {@html displayName}
        </span>
      </div>
      {#if selectedTool.value?.type !== ToolType.Fusion && !interpolated}
        <div class="flex items-center mr-4">
          {#if [BaseSchema.BBox, BaseSchema.Mask, BaseSchema.Keypoints].includes(trackChild.table_info.base_schema)}
            <IconButton
              tooltipContent="Edit object"
              selected={trackChild.ui.displayControl.editing}
              onclick={() => onEditIconClick(trackChild)}
            >
              <Pencil class="h-4" />
            </IconButton>
          {/if}
          <IconButton
            tooltipContent="Delete object"
            redconfirm
            onclick={() => onDeleteTrackItemClick(child, trackChild.ui.frame_index, trackChild)}
          >
            <Trash weight="regular" class="h-4" />
          </IconButton>
        </div>
      {/if}
    </div>
  {/each}
{/if}
