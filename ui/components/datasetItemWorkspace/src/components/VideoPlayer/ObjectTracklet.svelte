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
  import type { Tracklet, VideoObject, VideoItemBBox } from "@pixano/core";
  import { currentFrameIndex, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import TrackletKeyBox from "./TrackletKeyBox.svelte";
  import {
    colorScale,
    itemObjects,
    selectedTool,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { highlightCurrentObject } from "../../lib/api/objectsApi";
  import { panTool } from "../../lib/settings/selectionTools";
  import { filterTrackletBoxes, getNewTrackletValues } from "../../lib/api/videoApi";

  export let object: VideoObject;
  export let tracklet: Tracklet;
  export let onContextMenu: (event: MouseEvent) => void;
  export let onEditKeyBoxClick: (box: VideoItemBBox) => void;
  export let onAddKeyBoxClick: () => void;
  export let onSplitTrackletClick: () => void;
  export let onDeleteTrackletClick: () => void;
  export let findNeighborBoxes: (tracklet: Tracklet, frameIndex: number) => [number, number];
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
  ) => {
    const [prevFrameIndex, nextFrameIndex] = findNeighborBoxes(tracklet, newFrameIndex);
    if (newFrameIndex < prevFrameIndex || newFrameIndex >= nextFrameIndex) return;

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
  };

  const filterTracklet = (
    newFrameIndex: VideoItemBBox["frame_index"],
    draggedFrameIndex: VideoItemBBox["frame_index"],
  ) => {
    itemObjects.update((oldObjects) =>
      filterTrackletBoxes(newFrameIndex, draggedFrameIndex, tracklet, oldObjects, object.id),
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
    <ContextMenu.Item inset on:click={onAddKeyBoxClick}>Add a point</ContextMenu.Item>
    <ContextMenu.Item inset on:click={onSplitTrackletClick}>Split tracklet</ContextMenu.Item>
    <ContextMenu.Item inset on:click={onDeleteTrackletClick}>Delete tracklet</ContextMenu.Item>
  </ContextMenu.Content>
</ContextMenu.Root>
{#key tracklet.boxes.length}
  {#each tracklet.boxes as box}
    {#if box.is_key}
      <TrackletKeyBox
        {box}
        {color}
        {oneFrameInPixel}
        {onEditKeyBoxClick}
        objectId={object.id}
        {updateTrackletWidth}
        {filterTracklet}
      />
    {/if}
  {/each}
{/key}
