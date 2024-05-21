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

  import { ContextMenu } from "@pixano/core";
  import type { Tracklet, VideoItemBBox, VideoObject } from "@pixano/core";
  import { itemObjects } from "../../lib/stores/datasetItemWorkspaceStores";
  import {
    lastFrameIndex,
    currentFrameIndex,
    objectIdBeingEdited,
  } from "../../lib/stores/videoViewerStores";
  import { addKeyBox, findNeighbors, splitTrackletInTwo } from "../../lib/api/videoApi";
  import ObjectTracklet from "./ObjectTracklet.svelte";

  export let zoomLevel: number[];
  export let object: VideoObject;
  export let onTimeTrackClick: (imageIndex: number) => void;
  export let updateView: (frameIndex: number) => void;

  let rightClickFrameIndex: number;
  let objectTimeTrack: HTMLElement;

  $: totalWidth = ($lastFrameIndex / ($lastFrameIndex + 1)) * 100;

  const onContextMenu = (event: MouseEvent) => {
    itemObjects.update((objects) =>
      objects.map((obj) => {
        obj.highlighted = obj.id === object.id ? "self" : "none";
        obj.displayControl = {
          ...obj.displayControl,
          editing: false,
        };
        return obj;
      }),
    );
    const timeTrackPosition = objectTimeTrack.getBoundingClientRect();
    const rightClickFrame = (event.clientX - timeTrackPosition.left) / timeTrackPosition.width;
    rightClickFrameIndex = Math.round(rightClickFrame * $lastFrameIndex);
    onTimeTrackClick(rightClickFrameIndex);
  };

  const onEditKeyBoxClick = (box: VideoItemBBox) => {
    onTimeTrackClick(box.frame_index > $lastFrameIndex ? $lastFrameIndex : box.frame_index);
    objectIdBeingEdited.set(object.id);
    itemObjects.update((objects) =>
      objects.map((obj) => {
        obj.highlighted = obj.id === object.id ? "self" : "none";
        // obj.highlighted = isBeingEdited ? "all" : obj.highlighted;
        obj.displayControl = {
          ...obj.displayControl,
          editing: obj.id === object.id,
          // editing: !isBeingEdited && obj.id === object.id,
        };
        return obj;
      }),
    );
  };

  const onAddKeyBoxClick = () => {
    const box = { ...object.displayedBox, frame_index: rightClickFrameIndex, is_key: true };
    itemObjects.update((objects) =>
      addKeyBox(objects, box, object.id, rightClickFrameIndex, $lastFrameIndex),
    );
    onEditKeyBoxClick(box);
  };

  const onSplitTrackletClick = (trackletIndex: number) => {
    itemObjects.update((objects) =>
      objects.map((obj) => {
        if (obj.id === object.id && obj.datasetItemType === "video") {
          const newTrack = splitTrackletInTwo(obj, trackletIndex, rightClickFrameIndex);
          return { ...obj, track: newTrack };
        }
        return obj;
      }),
    );
  };

  const onDeleteTrackletClick = (trackletIndex: number) => {
    itemObjects.update((objects) =>
      objects.map((obj) => {
        if (obj.id === object.id && obj.datasetItemType === "video") {
          obj.track.splice(trackletIndex, 1);
        }
        return obj;
      }),
    );
  };

  const findNeighborKeyBoxes = (
    tracklet: Tracklet,
    frameIndex: VideoItemBBox["frame_index"],
  ): [number, number] => findNeighbors(object.track, tracklet, frameIndex, $lastFrameIndex);
</script>

<div
  class="flex gap-5 relative h-full my-auto"
  style={`width: ${zoomLevel[0]}%`}
  bind:this={objectTimeTrack}
>
  <span
    class="w-[1px] bg-primary h-full absolute top-0 z-30 pointer-events-none"
    style={`left: ${($currentFrameIndex / ($lastFrameIndex + 1)) * 100}%`}
  />
  <ContextMenu.Root>
    <ContextMenu.Trigger class="h-full w-full absolute left-0" style={`width: ${totalWidth}%`}>
      <p on:contextmenu|preventDefault={(e) => onContextMenu(e)} class="h-full w-full" />
    </ContextMenu.Trigger>
    <ContextMenu.Content>
      <ContextMenu.Item inset on:click={onAddKeyBoxClick}>Add a point</ContextMenu.Item>
    </ContextMenu.Content>
  </ContextMenu.Root>
  {#each object.track as tracklet, i}
    <ObjectTracklet
      {tracklet}
      {object}
      {onAddKeyBoxClick}
      {onContextMenu}
      {onEditKeyBoxClick}
      onSplitTrackletClick={() => onSplitTrackletClick(i)}
      onDeleteTrackletClick={() => onDeleteTrackletClick(i)}
      {findNeighborKeyBoxes}
      {updateView}
    />
  {/each}
</div>
