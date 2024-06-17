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
  import type { ItemObject, TrackletItem, VideoItemBBox } from "@pixano/core";
  import { itemObjects, selectedTool } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import { deleteKeyBoxFromTracklet } from "../../lib/api/videoApi";
  import { panTool } from "../../lib/settings/selectionTools";

  export let objectId: ItemObject["id"];

  export let item: TrackletItem;
  export let color: string;
  export let oneFrameInPixel: number;
  export let onEditKeyItemClick: (frameIndex: TrackletItem["frame_index"]) => void;
  export let updateTrackletWidth: (
    newIndex: TrackletItem["frame_index"],
    draggedIndex: TrackletItem["frame_index"],
  ) => boolean;
  export let filterTracklet: (
    newIndex: TrackletItem["frame_index"],
    draggedIndex: TrackletItem["frame_index"],
  ) => void;

  let isItemBeingEdited = false;

  $: {
    const currentObjectBeingEdited = $itemObjects.find((object) => object.displayControl?.editing);
    isItemBeingEdited =
      item.frame_index === $currentFrameIndex && currentObjectBeingEdited?.id === objectId;
  }

  const onDeleteItemClick = (item: TrackletItem) => {
    itemObjects.update((objects) => deleteKeyBoxFromTracklet(objects, item, objectId));
  };

  const getKeyItemLeftPosition = (frameIndex: VideoItemBBox["frame_index"]) => {
    const itemFrameIndex = frameIndex > $lastFrameIndex ? $lastFrameIndex : frameIndex;
    const leftPosition = (itemFrameIndex / ($lastFrameIndex + 1)) * 100;
    return leftPosition;
  };

  let left = getKeyItemLeftPosition(item.frame_index);

  const dragMe = (node: HTMLButtonElement) => {
    let moving = false;
    let startPosition: number;
    let startFrameIndex: number;
    let startOneFrameInPixel: number;
    let newFrameIndex: number | undefined;

    node.addEventListener("mousedown", (event) => {
      moving = true;
      startPosition = event.clientX;
      startFrameIndex = item.frame_index;
      startOneFrameInPixel = oneFrameInPixel;
      selectedTool.set(panTool);
    });

    window.addEventListener("mousemove", (event) => {
      if (moving) {
        const distance = event.clientX - startPosition;
        const raise = distance / startOneFrameInPixel;
        newFrameIndex = Math.round(startFrameIndex + raise);
        if (newFrameIndex < 0 || newFrameIndex > $lastFrameIndex) return;
        const canContinue = updateTrackletWidth(newFrameIndex, item.frame_index);
        if (canContinue) {
          left = getKeyItemLeftPosition(newFrameIndex);
        }
      }
    });

    window.addEventListener("mouseup", () => {
      moving = false;
      if (newFrameIndex !== undefined) filterTracklet(newFrameIndex, item.frame_index);
      newFrameIndex = undefined;
    });
  };
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn(
      "w-4 h-4 block bg-white border-2 rounded-full absolute left-[-0.5rem] top-1/2 translate-y-[-50%] translate-x-[-50%]",
      "hover:scale-150",
      { "bg-primary !border-primary": isItemBeingEdited },
    )}
    style={`left: ${left}%; border-color: ${color}`}
  >
    <button class="h-full w-full" use:dragMe />
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    <ContextMenu.Item inset on:click={() => onDeleteItemClick(item)}>Remove item</ContextMenu.Item>
    {#if !isItemBeingEdited}
      <ContextMenu.Item inset on:click={() => onEditKeyItemClick(item.frame_index)}
        >Edit item</ContextMenu.Item
      >
    {/if}
  </ContextMenu.Content>
</ContextMenu.Root>