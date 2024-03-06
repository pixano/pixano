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
  import type { ItemObject, BreakPointInterval, BreakPoint } from "@pixano/core";
  import { newShape, itemObjects } from "../../lib/stores/datasetItemWorkspaceStores";
  import { breakPointBeingEdited, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import { addBreakPointInInterval, deleteBreakPointInInterval } from "../../lib/api/videoApi";

  import VideoPlayerRow from "./VideoPlayerRow.svelte";

  export let zoomLevel: number[];
  export let object: ItemObject;
  export let colorScale: (id: string) => string;
  export let onTimeTrackClick: (imageIndex: number) => void;

  type Interval = BreakPointInterval & { width: number };

  let breakPointIntervals: Interval[] = [];
  let rightClickFrameIndex: number;
  let startIndex: number = 0;
  let startPosition: number = 0;
  let objectTimeTrack: HTMLElement;

  $: color = colorScale(object.id);

  $: {
    startIndex = object.bbox?.breakPointsIntervals?.[0]?.start || 0;
    startPosition = (startIndex / $lastFrameIndex) * 100;
  }

  const onContextMenu = (event: MouseEvent) => {
    newShape.set({
      status: "editing",
      type: "none",
      shapeId: object.id,
      highlighted: "self",
    });
    const rightClickFrame =
      (event.clientX - objectTimeTrack.offsetLeft) / objectTimeTrack.clientWidth;
    rightClickFrameIndex = Math.round(rightClickFrame * $lastFrameIndex);
    onTimeTrackClick(rightClickFrameIndex);
  };

  $: breakPointIntervals =
    object.bbox?.breakPointsIntervals?.map((interval) => {
      const end = interval.end > $lastFrameIndex ? $lastFrameIndex : interval.end;
      const width = ((end - interval.start) / ($lastFrameIndex + 1)) * 100;
      return { ...interval, width };
    }) || [];

  const onEditPointClick = (breakPoint: BreakPoint) => {
    breakPointBeingEdited.set(breakPoint);
    itemObjects.update((objects) =>
      objects.map((o) => {
        o.displayControl = {
          ...o.displayControl,
          editing: o.id === object.id,
        };
        return o;
      }),
    );
  };

  const onDeletePointClick = (breakPoint: BreakPoint) => {
    itemObjects.update((objects) => deleteBreakPointInInterval(objects, breakPoint, object.id));
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

  const getIntervalLeftPosition = (interval: Interval) => {
    return (interval.start / ($lastFrameIndex + 1)) * 100;
  };

  const getBreakPointLeftPosition = (breakPoint: BreakPoint) => {
    const breakPointFrameIndex =
      breakPoint.frameIndex > $lastFrameIndex ? $lastFrameIndex : breakPoint.frameIndex;
    return (breakPointFrameIndex / ($lastFrameIndex + 1)) * 100;
  };

  $: totalWidth = ($lastFrameIndex / ($lastFrameIndex + 1)) * 100;
</script>

<VideoPlayerRow>
  <p slot="name" class="z-40 py-4 sticky left-0 bg-white text-ellipsis overflow-hidden p-2">
    {object.id}
  </p>
  <div
    slot="timeTrack"
    class="flex gap-5 relative z-0 h-full my-auto"
    style={`width: ${zoomLevel[0]}%`}
    bind:this={objectTimeTrack}
  >
    <ContextMenu.Root>
      <ContextMenu.Trigger
        class="h-full w-full absolute"
        style={`left: ${startPosition}%; width: ${totalWidth}%`}
      >
        <p on:contextmenu|preventDefault={(e) => onContextMenu(e)} class="h-full w-full" />
      </ContextMenu.Trigger>
      <ContextMenu.Content>
        <ContextMenu.Item inset on:click={onAddPointClick}>Add a point</ContextMenu.Item>
      </ContextMenu.Content>
    </ContextMenu.Root>
    {#each breakPointIntervals as interval}
      <ContextMenu.Root>
        <ContextMenu.Trigger
          class={cn("h-4/5 w-full absolute z-0 top-1/2 -translate-y-1/2")}
          style={`left: ${getIntervalLeftPosition(interval)}%; width: ${interval.width}%; background-color: ${color}`}
        >
          <p on:contextmenu|preventDefault={(e) => onContextMenu(e)} class="h-full w-full" />
        </ContextMenu.Trigger>
        <ContextMenu.Content>
          <ContextMenu.Item inset on:click={onAddPointClick}>Add a point</ContextMenu.Item>
        </ContextMenu.Content>
      </ContextMenu.Root>
      {#each interval.breakPoints as breakPoint}
        <ContextMenu.Root>
          <ContextMenu.Trigger
            class={cn(
              "w-4 h-4 block bg-white border-2 rounded-full absolute left-[-0.5rem] top-1/2 translate-y-[-50%] translate-x-[-50%]",
              "hover:scale-150",
            )}
            style={`left: ${getBreakPointLeftPosition(breakPoint)}%; border-color: ${color}`}
          />
          <ContextMenu.Content>
            <ContextMenu.Item inset on:click={() => onDeletePointClick(breakPoint)}
              >Remove point</ContextMenu.Item
            >
            <ContextMenu.Item inset on:click={() => onEditPointClick(breakPoint)}
              >Edit point</ContextMenu.Item
            >
          </ContextMenu.Content>
        </ContextMenu.Root>
      {/each}
    {/each}
  </div>
</VideoPlayerRow>
