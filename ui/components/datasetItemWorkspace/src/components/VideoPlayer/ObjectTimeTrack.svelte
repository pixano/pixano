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
  import type { ItemObject, BreakPoint, BreakPointInterval } from "@pixano/core";
  import { itemObjects } from "../../lib/stores/datasetItemWorkspaceStores";
  import { breakPointBeingEdited, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import { addBreakPointInInterval, findNeighbors } from "../../lib/api/videoApi";
  import ObjectTimeInterval from "./ObjectTimeInterval.svelte";

  export let zoomLevel: number[];
  export let currentImageIndex: number;
  export let object: ItemObject;
  export let colorScale: (id: string) => string;
  export let onTimeTrackClick: (imageIndex: number) => void;

  let rightClickFrameIndex: number;
  let objectTimeTrack: HTMLElement;

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

  const isBreakPointBeingEdited = (breakPoint: BreakPoint) =>
    $breakPointBeingEdited?.objectId === object.id &&
    breakPoint.frameIndex === $breakPointBeingEdited?.frameIndex;

  const onEditPointClick = (breakPoint: BreakPoint) => {
    const isBeingEdited = isBreakPointBeingEdited(breakPoint);
    breakPointBeingEdited.set(isBeingEdited ? null : { ...breakPoint, objectId: object.id });
    onTimeTrackClick(
      breakPoint.frameIndex > $lastFrameIndex ? $lastFrameIndex : breakPoint.frameIndex,
    );
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

  const onAddPointClick = () => {
    const [x, y] = object.bbox?.coords || [0, 0];
    const breakPoint: BreakPoint = { frameIndex: rightClickFrameIndex, x, y };
    itemObjects.update((objects) =>
      addBreakPointInInterval(
        objects,
        breakPoint,
        object.id,
        rightClickFrameIndex,
        $lastFrameIndex,
      ),
    );
    onEditPointClick(breakPoint);
  };

  const findNeighborBreakPoints = (
    interval: BreakPointInterval,
    frameIndex: BreakPoint["frameIndex"],
  ): [number, number] => {
    if (!object.bbox?.breakPointsIntervals) return [0, 0];
    return findNeighbors(object.bbox.breakPointsIntervals, interval, frameIndex, $lastFrameIndex);
  };

  $: totalWidth = ($lastFrameIndex / ($lastFrameIndex + 1)) * 100;
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
      <ContextMenu.Item inset on:click={onAddPointClick}>Add a point</ContextMenu.Item>
    </ContextMenu.Content>
  </ContextMenu.Root>
  {#each object.bbox?.breakPointsIntervals || [] as interval}
    <ObjectTimeInterval
      {interval}
      {object}
      color={colorScale(object.id)}
      {onAddPointClick}
      {onContextMenu}
      {onEditPointClick}
      {findNeighborBreakPoints}
    />
  {/each}
</div>
