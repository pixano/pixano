<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onMount } from "svelte";

  import { ToolType } from "@pixano/canvas2d/src/tools";
  import {
    Annotation,
    BaseSchema,
    cn,
    ContextMenu,
    SequenceFrame,
    Tracklet,
    View,
    type SaveItem,
    type TrackletItem,
  } from "@pixano/core";
  import Button from "@pixano/core/src/components/ui/button/button.svelte";

  import { sourcesStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import {
    addOrUpdateSaveItem,
    getPixanoSource,
    getTopEntity,
    relink,
  } from "../../lib/api/objectsApi";
  import { sortByFrameIndex } from "../../lib/api/videoApi";
  import {
    annotations,
    colorScale,
    entities,
    saveData,
    selectedTool,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import RelinkAnnotation from "../SaveShape/RelinkAnnotation.svelte";
  import TrackletKeyItem from "./TrackletKeyItem.svelte";

  type MView = Record<string, View | View[]>;

  export let trackId: string;
  export let tracklet: Tracklet;
  export let views: MView;
  export let onContextMenu: (tracklet: Tracklet) => void;
  export let onEditKeyItemClick: (
    frameIndex: TrackletItem["frame_index"],
    viewname: string,
  ) => void;
  export let onAddKeyItemClick: (event: MouseEvent) => void;
  export let onSplitTrackletClick: () => void;
  export let onDeleteTrackletClick: () => void;
  //export let onRelinkTrackletClick: () => void;
  export let findNeighborItems: (tracklet: Tracklet, frameIndex: number) => [number, number];
  export let moveCursorToPosition: (clientX: number) => void;
  export let resetTool: () => void;

  let showRelink = false;
  let selectedEntityId = "new";
  let mustMerge: boolean = false;
  let overlapTargetId: string = "";

  const getLeft = (tracklet: Tracklet) => {
    let start = Math.max(0, tracklet.data.start_timestep - 0.5);
    return (start / ($lastFrameIndex + 1)) * 100;
  };
  const getRight = (tracklet: Tracklet) => {
    let end = Math.max(tracklet.data.start_timestep, tracklet.data.end_timestep) + 0.5;
    return (end / ($lastFrameIndex + 1)) * 100;
  };
  const getHeight = (views: MView) => 80 / Object.keys(views).length;
  const getTop = (tracklet: Tracklet, views: MView) => {
    return (
      10 +
      (80 * Object.keys(views).indexOf(tracklet.data.view_ref.name)) / Object.keys(views).length
    );
  };

  $: left = getLeft(tracklet);
  $: right = getRight(tracklet);
  let height: number = getHeight(views);
  let top: number = getTop(tracklet, views);
  let trackletElement: HTMLElement;

  let resizeObs: ResizeObserver;
  let oneFrameInPixel: number;
  const calcOneFrameInPixel = () => {
    oneFrameInPixel =
      trackletElement?.getBoundingClientRect().width /
      (tracklet.data.end_timestep - tracklet.data.start_timestep + 1);
  };
  calcOneFrameInPixel();

  $: if (resizeObs) {
    if (tracklet.ui.displayControl.highlighted) {
      resizeObs.observe(trackletElement);
    } else {
      resizeObs.unobserve(trackletElement);
    }
  }
  onMount(() => {
    resizeObs = new ResizeObserver(calcOneFrameInPixel);
  });

  $: color = $colorScale[1](trackId);

  $: tracklet_annotations_frame_indexes = tracklet.ui.childs.map((ann) => ann.ui.frame_index!);

  $: canAddKeyFrame =
    $currentFrameIndex > tracklet.data.start_timestep &&
    $currentFrameIndex < tracklet.data.end_timestep &&
    !tracklet.ui.childs.some((ann) => ann.ui.frame_index === $currentFrameIndex);

  $: canSplit =
    $currentFrameIndex >= tracklet.data.start_timestep &&
    $currentFrameIndex < tracklet.data.end_timestep;

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
      (nextFrameIndex !== $lastFrameIndex && newFrameIndex > nextFrameIndex - 1)
    )
      return false;
    const isStart = draggedFrameIndex === tracklet.data.start_timestep;
    const isEnd = draggedFrameIndex === tracklet.data.end_timestep;
    if (!(isStart || isEnd)) return false;
    if (isStart) {
      if (newFrameIndex >= tracklet.data.end_timestep) return false;
      left = (newFrameIndex / ($lastFrameIndex + 1)) * 100;
      right = (tracklet.data.end_timestep / ($lastFrameIndex + 1)) * 100;
    }
    if (isEnd) {
      if (newFrameIndex <= tracklet.data.start_timestep) return false;
      right = (newFrameIndex / ($lastFrameIndex + 1)) * 100;
    }
    return true;
  };

  const updateTrackletWidth = (newFrameIndex: number, draggedFrameIndex: number) => {
    const isStart = draggedFrameIndex === tracklet.data.start_timestep;
    const isEnd = draggedFrameIndex === tracklet.data.end_timestep;
    const newViewId = (views[tracklet.data.view_ref.name] as SequenceFrame[])[newFrameIndex].id;
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
      object: tracklet,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_tracklet_resized));
    movedAnn.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
    const save_ann_moved: SaveItem = {
      change_type: "update",
      object: movedAnn,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_ann_moved));
    currentFrameIndex.set(newFrameIndex);
  };

  $: leftTracklet = getNeighborTracklet($annotations, "left");
  $: rightTracklet = getNeighborTracklet($annotations, "right");

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
        object: neighbor,
      }),
    );
  };

  const onClick = (button: number, clientX: number) => {
    if (button === 0) {
      moveCursorToPosition(clientX);
      resetTool();
    }
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
          $selectedTool.type === ToolType.Fusion) ||
        tracklet.ui.displayControl.hidden,
    })}
    style={`left: ${left}%; width: ${right - left}%; top: ${top}%; height: ${height}%; background-color: ${color}`}
  >
    <button
      on:contextmenu|preventDefault={() => onContextMenu(tracklet)}
      class="absolute h-full w-full"
      bind:this={trackletElement}
      on:click={(e) => onClick(e.button, e.clientX)}
    />
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    {#if canAddKeyFrame}
      <ContextMenu.Item on:click={(event) => onAddKeyItemClick(event)}>
        Add a point at frame {$currentFrameIndex}
      </ContextMenu.Item>
    {/if}
    {#if canSplit}
      <ContextMenu.Item on:click={onSplitTrackletClick}>
        Split tracklet after frame {$currentFrameIndex}
      </ContextMenu.Item>
    {/if}
    {#if $selectedTool.type !== ToolType.Fusion}
      {#if leftTracklet}
        <ContextMenu.Item on:click={() => onGlueTrackletClick("left")}>
          Glue to left
        </ContextMenu.Item>
      {/if}
      {#if rightTracklet}
        <ContextMenu.Item on:click={() => onGlueTrackletClick("right")}>
          Glue to right
        </ContextMenu.Item>
      {/if}
      <ContextMenu.Item on:click={onRelinkTrackletClick}>Relink tracklet</ContextMenu.Item>
    {/if}
    <ContextMenu.Item on:click={onDeleteTrackletClick}>Delete tracklet</ContextMenu.Item>
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
        <Button class="text-white mt-4" on:click={handleRelink}>OK</Button>
      </div>
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
