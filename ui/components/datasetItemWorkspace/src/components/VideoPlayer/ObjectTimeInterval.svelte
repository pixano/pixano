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
  import type { ItemObject, BreakPoint, BreakPointInterval } from "@pixano/core";
  import { breakPointBeingEdited, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import IntervalBreakPoint from "./IntervalBreakPoint.svelte";

  export let object: ItemObject;
  export let color: string;
  export let interval: BreakPointInterval;
  export let onContextMenu: (event: MouseEvent) => void;
  export let onEditPointClick: (breakPoint: BreakPoint) => void;
  export let onAddPointClick: () => void;
  export let findNeighborBreakPoints: (
    interval: BreakPointInterval,
    frameIndex: number,
  ) => [number, number];

  const getLeft = (interval: BreakPointInterval) => (interval.start / ($lastFrameIndex + 1)) * 100;
  const getWidth = (interval: BreakPointInterval) => {
    const end = interval.end > $lastFrameIndex ? $lastFrameIndex : interval.end;
    return ((end - interval.start) / ($lastFrameIndex + 1)) * 100;
  };

  let width: number = getWidth(interval);
  let left: number = getLeft(interval);
  $: width = getWidth(interval);
  $: left = getLeft(interval);

  let tempFrameIndex: number | undefined;
  let oneFrameInPixel: number | undefined;

  const updateWidth = (distance: number, frameIndex: BreakPoint["frameIndex"]) => {
    if (!distance) return;
    tempFrameIndex = tempFrameIndex || frameIndex || 0;
    oneFrameInPixel =
      oneFrameInPixel ||
      intervalElement?.getBoundingClientRect().width / (interval.end - interval.start + 1);

    const raise = distance / oneFrameInPixel;
    const newFrameIndex = tempFrameIndex + raise;

    const [prevFrameIndex, nextFrameIndex] = findNeighborBreakPoints(interval, frameIndex);

    if (newFrameIndex < prevFrameIndex + 1 || newFrameIndex > nextFrameIndex - 1) return;

    interval.breakPoints = interval.breakPoints.map((breakPoint) => {
      if (tempFrameIndex && breakPoint.frameIndex === frameIndex) {
        breakPoint.frameIndex = Math.round(newFrameIndex);
        breakPointBeingEdited.set({
          ...breakPoint,
          objectId: object.id,
          frameIndex: breakPoint.frameIndex,
        });
      }
      return breakPoint;
    });
    interval.start = interval.breakPoints[0].frameIndex;
    interval.end = interval.breakPoints[interval.breakPoints.length - 1].frameIndex;
  };

  const onBreakPointDragEnd = () => {
    // TODO : save new values
    tempFrameIndex = undefined;
    oneFrameInPixel = undefined;
  };

  const isBreakPointBeingEdited = (breakPoint: BreakPoint) =>
    $breakPointBeingEdited?.objectId === object.id &&
    breakPoint.frameIndex === $breakPointBeingEdited?.frameIndex;
  let intervalElement: HTMLElement;
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn("h-4/5 w-full absolute top-1/2 -translate-y-1/2")}
    style={`left: ${left}%; width: ${width}%; background-color: ${color}`}
  >
    <button
      on:contextmenu|preventDefault={(e) => onContextMenu(e)}
      class="h-full w-full"
      bind:this={intervalElement}
    />
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    <ContextMenu.Item inset on:click={onAddPointClick}>Add a point</ContextMenu.Item>
  </ContextMenu.Content>
</ContextMenu.Root>
{#each interval.breakPoints as breakPoint}
  <IntervalBreakPoint
    {breakPoint}
    {color}
    isBeingEdited={isBreakPointBeingEdited(breakPoint)}
    {onEditPointClick}
    objectId={object.id}
    {updateWidth}
    {onBreakPointDragEnd}
  />
{/each}
