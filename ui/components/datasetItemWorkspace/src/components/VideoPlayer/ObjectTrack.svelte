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
  import { itemObjects, selectedTool } from "../../lib/stores/datasetItemWorkspaceStores";
  import {
    lastFrameIndex,
    currentFrameIndex,
    objectIdBeingEdited,
    videoControls,
  } from "../../lib/stores/videoViewerStores";
  import { addKeyBox, findNeighbors, splitTrackletInTwo } from "../../lib/api/videoApi";
  import ObjectTracklet from "./ObjectTracklet.svelte";
  import { panTool } from "../../lib/settings/selectionTools";
  import { highlightCurrentObject } from "../../lib/api/objectsApi";

  export let object: VideoObject;
  export let onTimeTrackClick: (imageIndex: number) => void;
  export let updateView: (frameIndex: number) => void;

  let rightClickFrameIndex: number;
  let objectTimeTrack: HTMLElement;

  $: totalWidth = ($lastFrameIndex / ($lastFrameIndex + 1)) * 100;

  const moveCursorToPosition = (clientX: number) => {
    const timeTrackPosition = objectTimeTrack.getBoundingClientRect();
    const rightClickFrame = (clientX - timeTrackPosition.left) / timeTrackPosition.width;
    rightClickFrameIndex = Math.round(rightClickFrame * $lastFrameIndex);
    onTimeTrackClick(rightClickFrameIndex);
  };

  const onContextMenu = (event: MouseEvent) => {
    itemObjects.update((oldObjects) => highlightCurrentObject(oldObjects, object));
    moveCursorToPosition(event.clientX);
    selectedTool.set(panTool);
  };

  const onEditKeyBoxClick = (box: VideoItemBBox) => {
    onTimeTrackClick(box.frame_index > $lastFrameIndex ? $lastFrameIndex : box.frame_index);
    objectIdBeingEdited.set(object.id);
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

  let showThumbnail = false;
  let thumbnailPosition = 0;

  const changeThumbnailPosition = (mouseClientX: number) => {
    const timeTrackPosition = objectTimeTrack.getBoundingClientRect();
    thumbnailPosition = mouseClientX - timeTrackPosition.x + 20;
  };
</script>

<div
  class="flex gap-5 relative h-12 my-auto z-20"
  id={`video-object-${object.id}`}
  style={`width: ${$videoControls.zoomLevel[0]}%`}
  bind:this={objectTimeTrack}
  on:mouseenter={() => (showThumbnail = true)}
  on:mouseleave={() => (showThumbnail = false)}
  on:mousemove={(e) => changeThumbnailPosition(e.clientX)}
  role="complementary"
>
  {#if showThumbnail}
    <div class="absolute top-[30%] z-40" style={`left: ${thumbnailPosition}px`}>
      <slot />
    </div>
  {/if}
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
      {moveCursorToPosition}
    />
  {/each}
</div>
