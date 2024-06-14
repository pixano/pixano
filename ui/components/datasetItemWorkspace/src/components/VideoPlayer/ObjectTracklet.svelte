<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

  import { ContextMenu, cn } from "@pixano/core";
  import type {
    Tracklet,
    VideoObject,
    VideoItemBBox,
    TrackletWithItems,
    TrackletItem,
  } from "@pixano/core";
  import { currentFrameIndex, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import TrackletKeyBox from "./TrackletKeyItem.svelte";
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
  export let onContextMenu: (event: MouseEvent) => void;
  export let onEditKeyItemClick: (frameIndex: TrackletItem["frame_index"]) => void;
  export let onAddKeyItemClick: () => void;
  export let onSplitTrackletClick: () => void;
  export let onDeleteTrackletClick: () => void;
  export let findNeighborItems: (frameIndex: number) => [number, number];
  export let updateView: (frameIndex: number, track: Tracklet[] | undefined) => void;
  export let moveCursorToPosition: (clientX: number) => void;

  const getLeft = (tracklet: Tracklet) => (tracklet.start / ($lastFrameIndex + 1)) * 100;
  const getWidth = (tracklet: Tracklet) => {
    const end = tracklet.end > $lastFrameIndex ? $lastFrameIndex : tracklet.end;
    return ((end - tracklet.start) / ($lastFrameIndex + 1)) * 100;
  };

  let width: number = getWidth(tracklet);
  let left: number = getLeft(tracklet);
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
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn("h-4/5 w-full absolute top-1/2 -translate-y-1/2", {
      "opacity-100": object.highlighted === "self",
      "opacity-30": object.highlighted === "none",
    })}
    style={`left: ${left}%; width: ${width}%; background-color: ${color}`}
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
    <ContextMenu.Item inset on:click={onAddKeyItemClick}>Add a point</ContextMenu.Item>
    <ContextMenu.Item inset on:click={onSplitTrackletClick}>Split tracklet</ContextMenu.Item>
    <ContextMenu.Item inset on:click={onDeleteTrackletClick}>Delete tracklet</ContextMenu.Item>
  </ContextMenu.Content>
</ContextMenu.Root>
{#key tracklet.items.length}
  {#each tracklet.items as item}
    {#if item.is_key}
      <TrackletKeyBox
        {item}
        {color}
        {oneFrameInPixel}
        {onEditKeyItemClick}
        objectId={object.id}
        {updateTrackletWidth}
        {filterTracklet}
      />
    {/if}
  {/each}
{/key}
