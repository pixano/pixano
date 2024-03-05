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
  import { deleteBreakPointInInterval } from "../../lib/api/videoApi";

  export let videoSpeed: number;
  export let zoomLevel: number[];
  export let object: ItemObject;
  export let videoTotalLengthInMs: number;
  export let onPlayerClick: (event: MouseEvent) => void;

  type Interval = BreakPointInterval & { width: number };

  let breakPointIntervals: Interval[] = [];
  let rightClickPosition: number;
  let startIndex: number = 0;
  let endIndex: number = 1;
  let startPosition: number = 0;
  let width: number = 0;

  $: {
    startIndex = object.bbox?.breakPointsIntervals?.[0]?.start || 0;
    endIndex = object.bbox?.breakPointsIntervals?.at(-1)?.end || 1;
    endIndex = endIndex > $lastFrameIndex ? $lastFrameIndex : endIndex;
    startPosition = ((startIndex * videoSpeed) / videoTotalLengthInMs) * 100;
    width = (((endIndex - startIndex) * videoSpeed) / videoTotalLengthInMs) * 100;
  }

  const onContextMenu = (event: MouseEvent) => {
    newShape.set({
      status: "editing",
      type: "none",
      shapeId: object.id,
      highlighted: "self",
    });
    onPlayerClick(event);
    const target = event.target as HTMLDivElement;
    rightClickPosition = event.offsetX / target.clientWidth;
  };

  $: breakPointIntervals =
    object.bbox?.breakPointsIntervals?.map((interval) => {
      const end = interval.end > $lastFrameIndex ? $lastFrameIndex : interval.end;
      const width = (((end - interval.start) * videoSpeed) / videoTotalLengthInMs) * 100;
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
    const frameIndex = Math.round((rightClickPosition * videoTotalLengthInMs) / videoSpeed);
    const breakPoint: BreakPoint = {
      frameIndex,
      x: object.bbox?.coords[0] || 0,
      y: object.bbox?.coords[1] || 0,
    };

    itemObjects.update((objects) =>
      objects.map((obj) => {
        // if (object.id === obj.id && obj.bbox) {
        //   if (!obj.bbox?.coordinates) {
        //     obj.bbox.coordinates = [];
        //   }
        //   obj.bbox.coordinates.push(pointCoordinate);
        //   obj.bbox.coordinates.sort((a, b) => a.frameIndex - b.frameIndex);
        // }
        return obj;
      }),
    ),
      onEditPointClick(breakPoint);
  };

  const getIntervalLeftPosition = (interval: Interval) => {
    return (interval.start / $lastFrameIndex) * 100;
  };

  const getBreakPointLeftPosition = (breakPoint: BreakPoint, interval: Interval) => {
    const breakPointFrameIndex =
      breakPoint.frameIndex > $lastFrameIndex ? $lastFrameIndex : breakPoint.frameIndex;
    const intervalEnd = interval.end > $lastFrameIndex ? $lastFrameIndex : interval.end;
    return ((breakPointFrameIndex - interval.start) / (intervalEnd - interval.start)) * 100;
  };
</script>

<div class="border-b border-slate-200 h-12 p-2 pl-0 w-full grid grid-cols-[25%_1fr]">
  <p class="sticky left-0 z-10 bg-white pl-2">{object.id}</p>
  <div class="w-full flex gap-5 relative" style={`width: ${zoomLevel[0]}%`}>
    <ContextMenu.Root>
      <ContextMenu.Trigger
        class="h-full w-full bg-emerald-100 absolute"
        style={`left: ${startPosition}% ; width: ${width}%`}
      >
        <p on:contextmenu|preventDefault={(e) => onContextMenu(e)} class="h-full w-full" />
      </ContextMenu.Trigger>
      <ContextMenu.Content>
        <ContextMenu.Item inset on:click={onAddPointClick}>Add a point</ContextMenu.Item>
      </ContextMenu.Content>
    </ContextMenu.Root>

    {#each breakPointIntervals as interval}
      <div
        class={cn("h-full w-full absolute z-0 bg-orange-500")}
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
      </div>
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
