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

  const isBreakPointBeingEdited = (breakPoint: BreakPoint) =>
    $breakPointBeingEdited?.objectId === object.id &&
    breakPoint.frameIndex === $breakPointBeingEdited?.frameIndex;

  const getIntervalLeftPosition = (interval: BreakPointInterval) => {
    return (interval.start / ($lastFrameIndex + 1)) * 100;
  };

  const getIntervalWidth = (interval: BreakPointInterval) => {
    const end = interval.end > $lastFrameIndex ? $lastFrameIndex : interval.end;
    const width = ((end - interval.start) / ($lastFrameIndex + 1)) * 100;
    return width;
  };
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn("h-4/5 w-full absolute top-1/2 -translate-y-1/2")}
    style={`left: ${getIntervalLeftPosition(interval)}%; width: ${getIntervalWidth(interval)}%; background-color: ${color}`}
  >
    <p on:contextmenu|preventDefault={(e) => onContextMenu(e)} class="h-full w-full" />
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    <ContextMenu.Item inset on:click={onAddPointClick}>Add a point</ContextMenu.Item>
  </ContextMenu.Content>
</ContextMenu.Root>
{#each interval.breakPoints as breakPoint}
  <IntervalBreakPoint
    {breakPoint}
    {color}
    {interval}
    isBeingEdited={isBreakPointBeingEdited(breakPoint)}
    {onEditPointClick}
    objectId={object.id}
  />
{/each}
