<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onMount } from "svelte";

  import { ToolType } from "$lib/tools";
  import {
    Annotation,
    BaseSchema,
    PrimaryButton,
    cn,
    ContextMenu,
    SequenceFrame,
    Tracklet,
    View,
    type SaveItem,
  } from "$lib/ui";

  import { sourcesStore } from "$lib/stores/appStores.svelte";
  import { addOrUpdateSaveItem } from "$lib/utils/saveItemUtils";
  import { sortByFrameIndex } from "$lib/utils/videoUtils";
  import { getPixanoSource, getTopEntity } from "$lib/utils/entityLookupUtils";
  import { relink } from "$lib/utils/entityMutations";
  import {
    annotations,
    colorScale,
    entities,
    saveData,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import { currentFrameIndex, lastFrameIndex } from "$lib/stores/videoStores.svelte";
  import RelinkAnnotation from "../SaveShape/RelinkAnnotation.svelte";
  import TrackletKeyItem from "./TrackletKeyItem.svelte";

  type MView = Record<string, View | View[]>;

  interface Props {
    trackId: string;
    tracklet: Tracklet;
    views: MView;
    onContextMenu: (tracklet: Tracklet) => void;
    onEditKeyItemClick: (
      frameIndex: number,
      viewname: string,
    ) => void;
    onAddKeyItemClick: (event: MouseEvent) => void;
    onSplitTrackletClick: () => void;
    onDeleteTrackletClick: () => void;
    findNeighborItems: (tracklet: Tracklet, frameIndex: number) => [number, number];
    moveCursorToPosition: (clientX: number) => void;
    resetTool: () => void;
  }

  let {
    trackId,
    tracklet = $bindable(),
    views,
    onContextMenu,
    onEditKeyItemClick,
    onAddKeyItemClick,
    onSplitTrackletClick,
    onDeleteTrackletClick,
    findNeighborItems,
    moveCursorToPosition,
    resetTool
  }: Props = $props();

  let showRelink = $state(false);
  let selectedEntityId = $state("new");
  let mustMerge: boolean = $state(false);
  let overlapTargetId: string = $state("");

  const tracklet_margin = 0.3;
  const getLeft = (tracklet: Tracklet) => {
    let start = Math.max(0, tracklet.data.start_timestep - tracklet_margin);
    return (start / (lastFrameIndex.value + 1)) * 100;
  };
  const getRight = (tracklet: Tracklet) => {
    let end = Math.max(tracklet.data.start_timestep, tracklet.data.end_timestep) + tracklet_margin;
    return (end / (lastFrameIndex.value + 1)) * 100;
  };
  const getHeight = (views: MView) => 80 / Object.keys(views).length;
  const getTop = (tracklet: Tracklet, views: MView) => {
    return (
      10 +
      (80 * Object.keys(views).indexOf(tracklet.data.view_ref.name)) / Object.keys(views).length
    );
  };

  let left = $derived(getLeft(tracklet));
  let right = $derived(getRight(tracklet));
  let height = $derived(getHeight(views));
  let top = $derived(getTop(tracklet, views));
  let trackletElement: HTMLElement = $state();

  let resizeObs: ResizeObserver = $state();
  let oneFrameInPixel: number = $state();
  const calcOneFrameInPixel = () => {
    oneFrameInPixel =
      trackletElement?.getBoundingClientRect().width /
      (tracklet.data.end_timestep - tracklet.data.start_timestep + 1);
  };
  calcOneFrameInPixel();

  $effect(() => {
    if (resizeObs) {
      if (tracklet.ui.displayControl.highlighted) {
        resizeObs.observe(trackletElement);
      } else {
        resizeObs.unobserve(trackletElement);
      }
    }
  });
  onMount(() => {
    resizeObs = new ResizeObserver(calcOneFrameInPixel);
  });

  let color = $derived(colorScale.value[1](trackId));

  let tracklet_annotations_frame_indexes = $derived((tracklet.ui.childs ?? []).map((ann) => ann.ui.frame_index!));

  let canAddKeyFrame =
    $derived(currentFrameIndex.value > tracklet.data.start_timestep &&
    currentFrameIndex.value < tracklet.data.end_timestep &&
    !(tracklet.ui.childs ?? []).some((ann) => ann.ui.frame_index === currentFrameIndex.value));

  let canSplit =
    $derived(currentFrameIndex.value >= tracklet.data.start_timestep &&
    currentFrameIndex.value < tracklet.data.end_timestep);

  const getNeighborTracklet = (
    annotations: Annotation[],
    direction: "left" | "right",
  ): Annotation | null => {
    const isLeft = direction === "left";

    const refCompareTimestep = isLeft ? tracklet.data.start_timestep : tracklet.data.end_timestep;

    const tracklets = annotations.filter((ann) => {
      if (!ann.is_type(BaseSchema.Tracklet)) return false;
      const t = ann as Tracklet;
      return (
        t.data.view_ref.name === tracklet.data.view_ref.name &&
        t.data.entity_ref.id === trackId &&
        (isLeft
          ? t.data.end_timestep < refCompareTimestep
          : t.data.start_timestep > refCompareTimestep)
      );
    });

    if (tracklets.length === 0) return null;

    return tracklets.reduce((best, curr) => {
      const tBest = best as Tracklet;
      const tCurr = curr as Tracklet;

      const bestVal = isLeft ? tBest.data.end_timestep : tBest.data.start_timestep;
      const currVal = isLeft ? tCurr.data.end_timestep : tCurr.data.start_timestep;

      return isLeft
        ? currVal > bestVal
          ? curr
          : best // max for "left"
        : currVal < bestVal
          ? curr
          : best; // min for "right"
    });
  };

  const canContinueDragging = (newFrameIndex: number, draggedFrameIndex: number): boolean => {
    const [prevFrameIndex, nextFrameIndex] = findNeighborItems(tracklet, draggedFrameIndex);
    if (
      (prevFrameIndex !== 0 && newFrameIndex < prevFrameIndex + 1) ||
      (nextFrameIndex !== lastFrameIndex.value && newFrameIndex > nextFrameIndex - 1)
    )
      return false;
    const isStart = draggedFrameIndex === tracklet.data.start_timestep;
    const isEnd = draggedFrameIndex === tracklet.data.end_timestep;
    if (!(isStart || isEnd)) return false;
    if (isStart) {
      if (newFrameIndex >= tracklet.data.end_timestep) return false;
      left = (newFrameIndex / (lastFrameIndex.value + 1)) * 100;
      right = (tracklet.data.end_timestep / (lastFrameIndex.value + 1)) * 100;
    }
    if (isEnd) {
      if (newFrameIndex <= tracklet.data.start_timestep) return false;
      right = (newFrameIndex / (lastFrameIndex.value + 1)) * 100;
    }
    return true;
  };

  const updateTrackletWidth = (newFrameIndex: number, draggedFrameIndex: number) => {
    const isStart = draggedFrameIndex === tracklet.data.start_timestep;
    const isEnd = draggedFrameIndex === tracklet.data.end_timestep;
    const viewFrames = views[tracklet.data.view_ref.name] as SequenceFrame[] | undefined;
    if (!viewFrames?.[newFrameIndex] || !tracklet.ui.childs?.length) return;
    const newViewId = viewFrames[newFrameIndex].id;
    let movedAnn = tracklet.ui.childs[0];
    if (isStart) tracklet.data.start_timestep = newFrameIndex;
    if (isEnd) {
      movedAnn = tracklet.ui.childs[tracklet.ui.childs.length - 1];
      tracklet.data.end_timestep = newFrameIndex;
    }
    movedAnn.ui.frame_index = newFrameIndex;
    movedAnn.data.view_ref.id = newViewId;

    annotations.update((objects) =>
      objects.map((ann) => {
        if (ann.is_type(BaseSchema.Tracklet) && ann.id === tracklet.id) {
          if (isStart) {
            (ann as Tracklet).data.start_timestep = newFrameIndex;
          }
          if (isEnd) {
            (ann as Tracklet).data.end_timestep = newFrameIndex;
          }
        }
        if (ann.id === movedAnn.id) {
          ann.ui.frame_index = newFrameIndex;
          ann.data.view_ref.id = newViewId;
        }
        return ann;
      }),
    );
    const pixSource = getPixanoSource(sourcesStore);
    tracklet.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
    const save_tracklet_resized: SaveItem = {
      change_type: "update",
      data: tracklet,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_tracklet_resized));
    movedAnn.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
    const save_ann_moved: SaveItem = {
      change_type: "update",
      data: movedAnn,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_ann_moved));
    currentFrameIndex.value = newFrameIndex;
  };

  let leftTracklet = $derived(getNeighborTracklet(annotations.value, "left"));
  let rightTracklet = $derived(getNeighborTracklet(annotations.value, "right"));

  const onGlueTrackletClick = (direction: "left" | "right") => {
    const neighbor = direction === "left" ? leftTracklet : rightTracklet;
    if (!neighbor) return;

    annotations.update((anns) => {
      // Remove neighbor
      let new_anns = anns.filter((ann) => ann.id !== neighbor.id);
      return new_anns.map((ann) => {
        if (ann.id === tracklet.id) {
          const currentTracklet = ann as Tracklet;
          const neighborTracklet = neighbor as Tracklet;

          // Add neighbor's childs
          currentTracklet.ui.childs = [
            ...currentTracklet.ui.childs,
            ...neighborTracklet.ui.childs,
          ].sort(sortByFrameIndex);

          // Update range
          if (direction === "left") {
            currentTracklet.data.start_timestep = neighborTracklet.data.start_timestep;
          } else {
            currentTracklet.data.end_timestep = neighborTracklet.data.end_timestep;
          }
        }
        return ann;
      });
    });

    entities.update((ents) =>
      ents.map((ent) => {
        if (ent.id === trackId) {
          ent.ui.childs = ent.ui.childs?.filter((ann) => ann.id !== neighbor.id);
        }
        return ent;
      }),
    );

    saveData.update((current_sd) =>
      addOrUpdateSaveItem(current_sd, {
        change_type: "delete",
        data: neighbor,
      }),
    );
  };

  const onClick = (button: number, clientX: number) => {
    if (button === 0) {
      moveCursorToPosition(clientX);
      resetTool();
    }
  };

  const handleTrackletContextMenu = (event: MouseEvent) => {
    event.preventDefault();
    onContextMenu(tracklet);
  };

  const onRelinkTrackletClick = (event: MouseEvent) => {
    event.preventDefault(); //avoid context menu close
    showRelink = !showRelink;
  };

  const handleRelink = () => {
    relink(tracklet, getTopEntity(tracklet), selectedEntityId, mustMerge, overlapTargetId);
    showRelink = false;
  };
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn("video-tracklet absolute scale-y-90 rounded-sm", {
      "opacity-100": tracklet.ui.displayControl.highlighted === "self",
      "opacity-30":
        (tracklet.ui.displayControl.highlighted === "none" &&
          selectedTool.value.type === ToolType.Fusion) ||
        tracklet.ui.displayControl.hidden,
    })}
    style={`left: ${left}%; width: ${right - left}%; top: ${top}%; height: ${height}%; background-color: ${color}`}
  >
    <button
      oncontextmenu={handleTrackletContextMenu}
      aria-label="Tracklet segment handle"
      class="absolute h-full w-full"
      bind:this={trackletElement}
      onclick={(e) => onClick(e.button, e.clientX)}
></button>
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    {#if selectedTool.value.type === ToolType.Fusion}
      <ContextMenu.Item>Context options disabled while in association mode</ContextMenu.Item>
    {:else}
      {#if canAddKeyFrame}
        <ContextMenu.Item onclick={(event) => onAddKeyItemClick(event)}>
          Add a point at frame {currentFrameIndex.value}
        </ContextMenu.Item>
      {/if}
      {#if canSplit}
        <ContextMenu.Item onclick={onSplitTrackletClick}>
          Split tracklet after frame {currentFrameIndex.value}
        </ContextMenu.Item>
      {/if}
      {#if leftTracklet}
        <ContextMenu.Item onclick={() => onGlueTrackletClick("left")}>
          Glue to left
        </ContextMenu.Item>
      {/if}
      {#if rightTracklet}
        <ContextMenu.Item onclick={() => onGlueTrackletClick("right")}>
          Glue to right
        </ContextMenu.Item>
      {/if}
      <ContextMenu.Item onclick={onRelinkTrackletClick}>Relink tracklet</ContextMenu.Item>
      <ContextMenu.Item onclick={onDeleteTrackletClick}>Delete tracklet</ContextMenu.Item>
      {#if showRelink}
        <div class="flex flex-row gap-4 items-center mr-4">
          <RelinkAnnotation
            bind:selectedEntityId
            bind:mustMerge
            bind:overlapTargetId
            baseSchema={tracklet.table_info.base_schema}
            viewRef={tracklet.data.view_ref}
            {tracklet}
          />
          <PrimaryButton class="text-white mt-4" onclick={handleRelink}>OK</PrimaryButton>
        </div>
      {/if}
    {/if}
  </ContextMenu.Content>
</ContextMenu.Root>
{#if tracklet.ui.displayControl.highlighted === "self" && oneFrameInPixel > 15}
  {#key tracklet_annotations_frame_indexes.length}
    {#each tracklet_annotations_frame_indexes as itemFrameIndex}
      <TrackletKeyItem
        {itemFrameIndex}
        {tracklet}
        {color}
        {height}
        {top}
        {oneFrameInPixel}
        {onEditKeyItemClick}
        {onClick}
        {trackId}
        {canContinueDragging}
        {updateTrackletWidth}
        {resetTool}
      />
    {/each}
  {/key}
{/if}
