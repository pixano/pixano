<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ContextMenu, cn } from "@pixano/core";
  import {
    Track,
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
  import { highlightCurrentObject, addOrUpdateSaveItem } from "../../lib/api/objectsApi";

  import { panTool } from "../../lib/settings/selectionTools";

  export let track: Track;
  export let tracklet: Tracklet;
  export let views: MView;
  export let onContextMenu: (event: MouseEvent, tracklet: Tracklet) => void;
  export let getTrackletItem: (ann: TrackletItem) => TrackletItem;
  export let onEditKeyItemClick: (frameIndex: TrackletItem["frame_index"]) => void;
  export let onAddKeyItemClick: (event: MouseEvent) => void;
  export let onSplitTrackletClick: () => void;
  export let onDeleteTrackletClick: () => void;
  export let findNeighborItems: (frameIndex: number) => [number, number];
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
  let tracklet_annotations: TrackletItem[];

  $: oneFrameInPixel =
    trackletElement?.getBoundingClientRect().width /
    (tracklet.data.end_timestep - tracklet.data.start_timestep + 1);
  $: color = $colorScale[1](track.id);

  $: {
    const tracklet_views: SequenceFrame[] = [];
    for (const view of Object.values(views)) {
      if (Array.isArray(view)) {
        for (const sf of view) {
          if (
            tracklet.data.entity_ref.id === track.id &&
            sf.data.frame_index >= tracklet.data.start_timestep &&
            sf.data.frame_index <= tracklet.data.end_timestep
          ) {
            tracklet_views.push(sf);
          }
        }
      }
    }
    const tracklet_views_ids: string[] = tracklet_views.map((sf) => sf.id);
    tracklet_annotations = $annotations.flatMap((ann) =>
      !ann.is_tracklet &&
      ann.data.entity_ref.id === track.id &&
      tracklet_views_ids.includes(ann.data.view_ref.id)
        ? [
            {
              frame_index: tracklet_views.find((sf) => sf.id === ann.data.view_ref.id)?.data
                .frame_index,
              tracklet_id: tracklet.id,
              is_key: true,
              is_thumbnail: false,
              hidden: false,
            } as TrackletItem,
          ]
        : [],
    );
  }

  const canContinueDragging = (newFrameIndex: number, draggedFrameIndex: number): boolean => {
    const [prevFrameIndex, nextFrameIndex] = findNeighborItems(draggedFrameIndex);
    if (
      newFrameIndex !== draggedFrameIndex &&
      (newFrameIndex < prevFrameIndex + 1 || newFrameIndex > nextFrameIndex - 1)
    )
      return false;
    const isStart = draggedFrameIndex === tracklet.data.start_timestep;
    const isEnd = draggedFrameIndex === tracklet.data.end_timestep;
    if (!(isStart || isEnd)) return false;
    if (isStart) {
      left = (newFrameIndex / ($lastFrameIndex + 1)) * 100;
      width = ((tracklet.data.end_timestep - newFrameIndex) / ($lastFrameIndex + 1)) * 100;
    }
    if (isEnd) {
      width = ((newFrameIndex - tracklet.data.start_timestep) / ($lastFrameIndex + 1)) * 100;
    }
    return true;
  };

  const updateTrackletWidth = (newFrameIndex: number, draggedFrameIndex: number) => {
    const [prevFrameIndex, nextFrameIndex] = findNeighborItems(draggedFrameIndex);
    if (newFrameIndex <= prevFrameIndex) newFrameIndex = prevFrameIndex + 1;
    if (newFrameIndex >= nextFrameIndex) newFrameIndex = nextFrameIndex - 1;
    const isStart = draggedFrameIndex === tracklet.data.start_timestep;
    const isEnd = draggedFrameIndex === tracklet.data.end_timestep;
    const newViewId = (views[tracklet.data.view_ref.name] as SequenceFrame[])[newFrameIndex].id;
    let movedAnn = tracklet.childs[0];
    if (isStart) tracklet.data.start_timestep = newFrameIndex;
    if (isEnd) {
      movedAnn = tracklet.childs[tracklet.childs.length - 1];
      tracklet.data.end_timestep = newFrameIndex;
    }
    movedAnn.frame_index = newFrameIndex;
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
          ann.frame_index = newFrameIndex;
          ann.data.view_ref.id = newViewId;
        }
        return ann;
      }),
    );
    const save_tracklet_resized: SaveItem = {
      change_type: "update",
      object: tracklet,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_tracklet_resized));
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
    annotations.update((objects) => highlightCurrentObject(objects, tracklet));
  };

  const onDoubleClick = () => {
    selectedTool.set(panTool);
    annotations.update((objects) =>
      objects.map((obj) => {
        obj.highlighted = obj.data.entity_ref.id === track.id ? "self" : "none";
        obj.displayControl = {
          ...obj.displayControl,
          editing: obj.data.entity_ref.id === track.id,
        };
        return obj;
      }),
    );
  };
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn("absolute border-y border-white", {
      "opacity-100": tracklet.highlighted === "self",
      "opacity-30": tracklet.highlighted === "none",
    })}
    style={`left: ${left}%; width: ${width}%; top: ${top}%; height: ${height}%; background-color: ${color}`}
  >
    <button
      on:contextmenu|preventDefault={(e) => onContextMenu(e, tracklet)}
      class="h-full w-full"
      bind:this={trackletElement}
      on:click={(e) => onClick(e.clientX)}
      on:dblclick={onDoubleClick}
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
{#each tracklet_annotations as ann}
  <TrackletKeyItem
    item={ann}
    {tracklet}
    {color}
    {height}
    {top}
    {oneFrameInPixel}
    {onEditKeyItemClick}
    trackId={track.id}
    {canContinueDragging}
    {updateTrackletWidth}
  />
{/each}
