<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ContextMenu, cn } from "@pixano/core";
  import {
    Tracklet,
    SequenceFrame,
    type TrackletItem,
    type MView,
    type SaveItem,
  } from "@pixano/core";
  import { currentFrameIndex, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import TrackletKeyItem from "./TrackletKeyItem.svelte";
  import {
    colorScale,
    annotations,
    selectedTool,
    saveData,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { sourcesStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import { addOrUpdateSaveItem, getPixanoSource } from "../../lib/api/objectsApi";

  import { panTool } from "../../lib/settings/selectionTools";

  export let trackId: string;
  export let tracklet: Tracklet;
  export let views: MView;
  export let onContextMenu: (event: MouseEvent, tracklet: Tracklet) => void;
  export let onEditKeyItemClick: (frameIndex: TrackletItem["frame_index"]) => void;
  export let onAddKeyItemClick: (event: MouseEvent) => void;
  export let onSplitTrackletClick: () => void;
  export let onDeleteTrackletClick: () => void;
  export let findNeighborItems: (tracklet: Tracklet, frameIndex: number) => [number, number];
  export let moveCursorToPosition: (clientX: number) => void;

  const getLeft = (tracklet: Tracklet) =>
    (tracklet.data.start_timestep / ($lastFrameIndex + 1)) * 100;
  const getWidth = (tracklet: Tracklet) => {
    const end =
      tracklet.data.end_timestep > $lastFrameIndex ? $lastFrameIndex : tracklet.data.end_timestep;
    return ((end - tracklet.data.start_timestep) / ($lastFrameIndex + 1)) * 100;
  };
  const getHeight = (views: MView) => 80 / Object.keys(views).length;
  const getTop = (tracklet: Tracklet, views: MView) => {
    return (
      10 +
      (80 * Object.keys(views).indexOf(tracklet.data.view_ref.name)) / Object.keys(views).length
    );
  };

  let width: number = getWidth(tracklet);
  let left: number = getLeft(tracklet);
  let height: number = getHeight(views);
  let top: number = getTop(tracklet, views);
  let trackletElement: HTMLElement;

  $: oneFrameInPixel =
    trackletElement?.getBoundingClientRect().width /
    (tracklet.data.end_timestep - tracklet.data.start_timestep + 1);
  $: color = $colorScale[1](trackId);

  $: tracklet_annotations_frame_indexes = tracklet.ui.childs.map((ann) => ann.ui.frame_index!);

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
      width = ((tracklet.data.end_timestep - newFrameIndex) / ($lastFrameIndex + 1)) * 100;
    }
    if (isEnd) {
      if (newFrameIndex <= tracklet.data.start_timestep) return false;
      width = ((newFrameIndex - tracklet.data.start_timestep) / ($lastFrameIndex + 1)) * 100;
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
        if (ann.is_tracklet && ann.id === tracklet.id) {
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

  const onClick = (clientX: number) => {
    moveCursorToPosition(clientX);
    selectedTool.set(panTool);
  };
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn("absolute scale-y-90", {
      "opacity-100": tracklet.ui.highlighted === "self",
      "opacity-30": tracklet.ui.highlighted === "none",
    })}
    style={`left: ${left}%; width: ${width}%; top: ${top}%; height: ${height}%; background-color: ${color}`}
  >
    <button
      on:contextmenu|preventDefault={(e) => onContextMenu(e, tracklet)}
      class="absolute h-full w-full"
      bind:this={trackletElement}
      on:click={(e) => onClick(e.clientX)}
    />
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    <ContextMenu.Item inset on:click={(event) => onAddKeyItemClick(event)}
      >Add a point</ContextMenu.Item
    >
    <ContextMenu.Item inset on:click={onSplitTrackletClick}>Split tracklet</ContextMenu.Item>
    <ContextMenu.Item inset on:click={onDeleteTrackletClick}>Delete tracklet</ContextMenu.Item>
  </ContextMenu.Content>
</ContextMenu.Root>
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
  />
{/each}
