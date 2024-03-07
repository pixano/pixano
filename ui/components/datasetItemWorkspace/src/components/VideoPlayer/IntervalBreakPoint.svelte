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
  import { itemObjects } from "../../lib/stores/datasetItemWorkspaceStores";
  import { breakPointBeingEdited, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import { deleteBreakPointInInterval } from "../../lib/api/videoApi";

  export let objectId: ItemObject["id"];

  export let breakPoint: BreakPoint;
  export let interval: BreakPointInterval;
  export let isBeingEdited: boolean;
  export let onEditPointClick: (breakPoint: BreakPoint) => void;
  export let color: string;

  $breakPointBeingEdited?.objectId === objectId &&
    breakPoint.frameIndex === $breakPointBeingEdited?.frameIndex;

  const onDeletePointClick = (breakPoint: BreakPoint) => {
    itemObjects.update((objects) => deleteBreakPointInInterval(objects, breakPoint, objectId));
  };

  const getBreakPointLeftPosition = (breakPoint: BreakPoint) => {
    const breakPointFrameIndex =
      breakPoint.frameIndex > $lastFrameIndex ? $lastFrameIndex : breakPoint.frameIndex;
    return (breakPointFrameIndex / ($lastFrameIndex + 1)) * 100;
  };

  const dragMe = (node: HTMLButtonElement) => {
    let moving = false;
    let startPosition: number;

    node.addEventListener("mousedown", (event) => {
      moving = true;
      startPosition = event.clientX;
    });

    window.addEventListener("mousemove", (event) => {
      if (moving) {
        console.log("moving", event);
        itemObjects.update((objects) => {
          const newObjects = objects.map((obj) => {
            if (obj.id === objectId && obj.bbox) {
              const currentInterval = obj.bbox.breakPointsIntervals?.find(
                (i) => i.start === interval.start,
              );

              const parentDimensions = node.parentElement?.getBoundingClientRect();
              if (!currentInterval || !parentDimensions) return obj;
              //   const left = event.clientX - (parentDimensions?.left || 0);
              //   const max = parentDimensions?.width || 1;
              //   const newFrameIndex = Math.floor((left / max) * $lastFrameIndex);
              //   const oneFrameDistance =
              //     interval.width / (currentInterval.end - currentInterval.start);
              const distance = event.clientX - startPosition;
              //   const newFrameIndex = breakPoint.frameIndex + Math.floor(distance / oneFrameDistance);
              console.log({
                distance,
                // oneFrameDistance,
                // newFrameIndex,
                parentDimensions,
                parent: node.parentElement,
                interval,
              });
              //   const newBreakPoints = obj.bbox?.breakPoints?.map((bp) => {
              //     if (bp.frameIndex === breakPoint.frameIndex) {
              //       bp.frameIndex = 0;
              //     }
              //     return bp;
              //   });
              const newBreakPoints = obj.bbox?.breakPointsIntervals;
              obj.bbox = { ...obj.bbox, breakPointsIntervals: newBreakPoints };
            }
            return obj;
          });
          return newObjects;
        });
        // currentImageIndex = getImageIndexFromMouseMove(event, node, imageFilesLength);
      }
    });

    window.addEventListener("mouseup", () => {
      moving = false;
    });
  };
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn(
      "w-4 h-4 block bg-white border-2 rounded-full absolute left-[-0.5rem] top-1/2 translate-y-[-50%] translate-x-[-50%]",
      "hover:scale-150",
      { "bg-primary !border-primary": isBeingEdited },
    )}
    style={`left: ${getBreakPointLeftPosition(breakPoint)}%; border-color: ${color}`}
  >
    <button class="h-full w-full" use:dragMe />
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    <ContextMenu.Item inset on:click={() => onDeletePointClick(breakPoint)}
      >Remove point</ContextMenu.Item
    >
    <ContextMenu.Item inset on:click={() => onEditPointClick(breakPoint)}>
      {isBeingEdited ? "Stop editing" : "Edit point"}
    </ContextMenu.Item>
  </ContextMenu.Content>
</ContextMenu.Root>
