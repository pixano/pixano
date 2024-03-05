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

  export let zoomLevel: number[];
  export let object: ItemObject;

  export let onTimeTrackClick: (imageIndex: number) => void;

  type Interval = BreakPointInterval & { width: number };

  let breakPointIntervals: Interval[] = [];
  let rightClickFrameIndex: number;
  let startIndex: number = 0;
  let startPosition: number = 0;
  let objectTimeTrack: HTMLElement;

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

<div class="border-b border-slate-200 h-12 w-full grid grid-cols-[25%_1fr]">
  <p class="sticky left-0 z-10 p-2 bg-white">{object.id}</p>
  <div
    class="flex gap-5 relative w-[calc(100%-1rem)] z-0"
    style={`width: ${zoomLevel[0]}%`}
    bind:this={objectTimeTrack}
  >
    <ContextMenu.Root>
      <ContextMenu.Trigger
        class="h-full w-full bg-emerald-100 absolute"
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
          class={cn("h-full w-full absolute z-0 bg-orange-200")}
          style={`left: ${getIntervalLeftPosition(interval)}%; width: ${interval.width}%`}
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
              "w-3 h-3 block bg-red-500 rounded-full absolute left-[-0.5rem] top-1/2 translate-y-[-50%] translate-x-[-50%]",
              "hover:scale-150",
            )}
            style={`left: ${getBreakPointLeftPosition(breakPoint)}%`}
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
      <!-- <div
        class={cn("h-full w-full absolute z-0 bg-orange-200")}
        style={`left: ${getIntervalLeftPosition(interval)}%; width: ${interval.width}%`}
      >
        {#each interval.breakPoints as breakPoint}
          <ContextMenu.Root>
            <ContextMenu.Trigger
              class="w-4 h-4 block bg-red-500 rounded-full absolute left-[-0.5rem] top-1/2 translate-y-[-50%] z-10"
              style={`left: ${getBreakPointLeftPosition(breakPoint, interval)}%`}
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
      </div> -->
    {/each}

    <!-- {#each inflexionCoordinates as inflexionPoint}
      <ContextMenu.Root>
        <ContextMenu.Trigger
          class="w-4 h-4 block bg-indigo-500 rounded-full absolute left-[-0.5rem] top-1/2 translate-y-[-50%] z-10"
          style={`left: ${((inflexionPoint.frameIndex * videoSpeed) / videoTotalLengthInMs) * 100}%`}
        />
        <ContextMenu.Content>
          <ContextMenu.Item inset on:click={() => onDeletePointClick(inflexionPoint)}
            >Remove point</ContextMenu.Item
          >
          <ContextMenu.Item inset on:click={() => onEditPointClick(inflexionPoint)}
            >Edit point</ContextMenu.Item
          >
        </ContextMenu.Content>
      </ContextMenu.Root>
    {/each} -->
    <!-- {#each directionSlots as slot}
      <div
        class="h-full w-full bg-yellow-500 absolute z-0"
        style={`left: ${slot.start}% ; width: ${slot.width}%`}
      />
    {/each} -->
  </div>
</div>
