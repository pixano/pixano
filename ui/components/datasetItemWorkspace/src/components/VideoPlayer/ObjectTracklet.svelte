<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ContextMenu, cn } from "@pixano/core";
  import type {
    Tracklet,
    VideoObject,
    VideoItemBBox,
    TrackletWithItems,
    TrackletItem,
  } from "@pixano/core";
  import { currentFrameIndex, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import TrackletKeyItem from "./TrackletKeyItem.svelte";
  import {
    colorScale,
    itemObjects,
    selectedTool,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { highlightCurrentObject } from "../../lib/api/objectsApi";
  import { panTool } from "../../lib/settings/selectionTools";
  import {
    filterTrackletItems,
    getNewTrackletValues,
    mapTrackletItems,
  } from "../../lib/api/videoApi";

  export let object: VideoObject;
  export let tracklet: TrackletWithItems;
  export let views: string[];
  export let onContextMenu: (event: MouseEvent) => void;
  export let getTrackletItem: (ann: TrackletItem) => TrackletItem;
  export let onEditKeyItemClick: (frameIndex: TrackletItem["frame_index"]) => void;
  export let onAddKeyItemClick: (event: MouseEvent) => void;
  export let onSplitTrackletClick: () => void;
  export let onDeleteTrackletClick: () => void;
  export let findNeighborItems: (frameIndex: number) => [number, number];
  export let updateView: (frameIndex: number, track: Tracklet[] | undefined) => void;
  export let updateTracks: () => void;
  export let moveCursorToPosition: (clientX: number) => void;

  const getLeft = (tracklet: Tracklet) => (tracklet.start / ($lastFrameIndex + 1)) * 100;
  const getWidth = (tracklet: Tracklet) => {
    const end = tracklet.end > $lastFrameIndex ? $lastFrameIndex : tracklet.end;
    return ((end - tracklet.start) / ($lastFrameIndex + 1)) * 100;
  };
  const getHeight = (views: string[]) => 80 / views.length;
  const getTop = (tracklet: Tracklet, views: string[]) => {
    return 10 + (80 * views.indexOf(tracklet.view_id)) / views.length;
  };

  let width: number = getWidth(tracklet);
  let left: number = getLeft(tracklet);
  let height: number = getHeight(views);
  let top: number = getTop(tracklet, views);
  let trackletElement: HTMLElement;

  $: oneFrameInPixel =
    trackletElement?.getBoundingClientRect().width / (tracklet.end - tracklet.start + 1);
  $: color = $colorScale[1](object.id);

  const updateTrackletWidth = (
    newFrameIndex: VideoItemBBox["frame_index"],
    draggedFrameIndex: VideoItemBBox["frame_index"],
  ): boolean => {
    const [prevFrameIndex, nextFrameIndex] = findNeighborItems(draggedFrameIndex);

    if (newFrameIndex < prevFrameIndex + 1 || newFrameIndex >= nextFrameIndex - 1) return false;

    const isStart = draggedFrameIndex === tracklet.start;
    const isEnd = draggedFrameIndex === tracklet.end;
    if (isStart) {
      left = (newFrameIndex / ($lastFrameIndex + 1)) * 100;
      width = ((tracklet.end - newFrameIndex) / ($lastFrameIndex + 1)) * 100;
    }
    if (isEnd) {
      width = ((newFrameIndex - tracklet.start) / ($lastFrameIndex + 1)) * 100;
    }
    const newTracklet = getNewTrackletValues(isStart, newFrameIndex, tracklet);
    updateView(newFrameIndex, [newTracklet]);
    //TODO canSave.set(true); //NO, it's done on dragMe > mouseUp (else too mush calls)
    currentFrameIndex.set(newFrameIndex);
    return true;
  };

  const filterTracklet = (
    newFrameIndex: VideoItemBBox["frame_index"],
    draggedFrameIndex: VideoItemBBox["frame_index"],
  ) => {
    tracklet = filterTrackletItems(newFrameIndex, draggedFrameIndex, tracklet);
    itemObjects.update((oldObjects) =>
      oldObjects.map((obj) => {
        if (obj.id === object.id && obj.datasetItemType === "video") {
          obj.track = obj.track.map((trackItem) => {
            if (trackItem.id === tracklet.id) {
              return tracklet;
            }
            return trackItem;
          });
          const { boxes, keypoints } = mapTrackletItems(obj, tracklet);
          obj.boxes = boxes;
          obj.keypoints = keypoints;
        }
        return obj;
      }),
    );
  };

  const onClick = (clientX: number) => {
    moveCursorToPosition(clientX);
    selectedTool.set(panTool);
    itemObjects.update((oldObjects) => highlightCurrentObject(oldObjects, object, false));
  };

  const onDoubleClick = () => {
    selectedTool.set(panTool);
    itemObjects.update((objects) =>
      objects.map((obj) => {
        obj.highlighted = obj.id === object.id ? "self" : "none";
        obj.displayControl = {
          ...obj.displayControl,
          editing: obj.id === object.id,
        };
        return obj;
      }),
    );
  };

  const updateTracklet = () => {
    const boxes = object.boxes
      ? object.boxes.filter(
          (box) =>
            box.view_id === tracklet.view_id &&
            box.frame_index >= tracklet.start &&
            box.frame_index <= tracklet.end,
        )
      : [];
    const keypoints = object.keypoints
      ? object.keypoints.filter(
          (kp) =>
            kp.view_id === tracklet.view_id &&
            kp.frame_index >= tracklet.start &&
            kp.frame_index <= tracklet.end,
        )
      : [];
    let items: TrackletItem[] = [];
    for (const ann of boxes) {
      items.push(getTrackletItem(ann));
    }
    for (const ann of keypoints) {
      const item = getTrackletItem(ann);
      if (!items.find((it) => it.frame_index == item.frame_index)) items.push(getTrackletItem(ann));
    }
    const new_tracklet = object.track.find((trklet) => trklet.id === tracklet.id);
    tracklet = {
      ...(new_tracklet ? new_tracklet : tracklet),
      items: items,
    };
    console.log("UpdTracklet", object, tracklet);
    updateTracks();
  };
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn("absolute border-y border-white", {
      "opacity-100": object.highlighted === "self",
      "opacity-30": object.highlighted === "none",
    })}
    style={`left: ${left}%; width: ${width}%; top: ${top}%; height: ${height}%; background-color: ${color}`}
  >
    <button
      on:contextmenu|preventDefault={(e) => onContextMenu(e)}
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
{#each tracklet.items as item}
  {#if item.is_key}
    <TrackletKeyItem
      {item}
      {color}
      {height}
      {top}
      {oneFrameInPixel}
      {onEditKeyItemClick}
      objectId={object.id}
      {updateTrackletWidth}
      {updateTracklet}
      {filterTracklet}
    />
  {/if}
{/each}
