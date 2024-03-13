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
  import type { BreakPoint, ItemBBox, Tracklet, VideoObject } from "@pixano/core";
  import { itemObjects } from "../../lib/stores/datasetItemWorkspaceStores";
  import { itemBoxBeingEdited, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import { addKeyBox, findNeighbors } from "../../lib/api/videoApi";
  import ObjectTracklet from "./ObjectTracklet.svelte";

  export let zoomLevel: number[];
  export let currentImageIndex: number;
  export let object: VideoObject;
  export let colorScale: (id: string) => string;
  export let onTimeTrackClick: (imageIndex: number) => void;

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

  const isKeyBoxBeingEdited = (box: ItemBBox) =>
    $itemBoxBeingEdited?.objectId === object.id &&
    box.frameIndex === $itemBoxBeingEdited?.frameIndex;

  const onEditKeyBoxClick = (box: ItemBBox) => {
    const isBeingEdited = isKeyBoxBeingEdited(box);
    itemBoxBeingEdited.set(isBeingEdited ? null : { ...box, objectId: object.id });
    onTimeTrackClick(box.frameIndex > $lastFrameIndex ? $lastFrameIndex : box.frameIndex);
    itemObjects.update((objects) =>
      objects.map((o) => {
        o.highlighted = o.id === object.id ? "self" : "none";
        o.displayControl = {
          ...o.displayControl,
          editing: !isBeingEdited && o.id === object.id,
        };
        return o;
      }),
    );
  };

  const onAddKeyBoxClick = () => {
    const box = { ...object.displayedBox, frameIndex: rightClickFrameIndex };
    itemObjects.update((objects) =>
      addKeyBox(objects, box, object.id, rightClickFrameIndex, $lastFrameIndex),
    );
    onEditKeyBoxClick(box);
  };

  const findNeighborKeyBoxes = (
    tracklet: Tracklet,
    frameIndex: BreakPoint["frameIndex"],
  ): [number, number] => findNeighbors(object.track, tracklet, frameIndex, $lastFrameIndex);
</script>

<div
  class="flex gap-5 relative h-full my-auto"
  style={`width: ${zoomLevel[0]}%`}
  bind:this={objectTimeTrack}
>
  <span
    class="w-[1px] bg-primary h-full absolute top-0 z-30 pointer-events-none"
    style={`left: ${(currentImageIndex / ($lastFrameIndex + 1)) * 100}%`}
  />
  <ContextMenu.Root>
    <ContextMenu.Trigger class="h-full w-full absolute left-0" style={`width: ${totalWidth}%`}>
      <p on:contextmenu|preventDefault={(e) => onContextMenu(e)} class="h-full w-full" />
    </ContextMenu.Trigger>
    <ContextMenu.Content>
      <ContextMenu.Item inset on:click={onAddKeyBoxClick}>Add a point</ContextMenu.Item>
    </ContextMenu.Content>
  </ContextMenu.Root>
  {#each object.track as tracklet}
    <ObjectTracklet
      {tracklet}
      {object}
      color={colorScale(object.id)}
      {onAddKeyBoxClick}
      {onContextMenu}
      {onEditKeyBoxClick}
      {findNeighborKeyBoxes}
    />
  {/each}
</div>
