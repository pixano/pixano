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
  import type { ItemObject, VideoItemBBox } from "@pixano/core";
  import { itemObjects, selectedTool } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import { deleteKeyBoxFromTracklet } from "../../lib/api/videoApi";
  import { panTool } from "../../lib/settings/selectionTools";

  export let objectId: ItemObject["id"];

  export let box: VideoItemBBox;
  export let color: string;
  export let oneFrameInPixel: number;
  export let onEditKeyBoxClick: (keyBox: VideoItemBBox) => void;
  export let updateTrackletWidth: (
    newIndex: VideoItemBBox["frame_index"],
    draggedIndex: VideoItemBBox["frame_index"],
  ) => void;
  export let filterTracklet: (
    newIndex: VideoItemBBox["frame_index"],
    draggedIndex: VideoItemBBox["frame_index"],
  ) => void;

  let isBoxBeingEdited = false;

  $: {
    const currentObjectBeingEdited = $itemObjects.find((object) => object.displayControl?.editing);
    isBoxBeingEdited =
      box.frame_index === $currentFrameIndex && currentObjectBeingEdited?.id === objectId;
  }

  const onDeleteKeyBoxClick = (box: VideoItemBBox) => {
    itemObjects.update((objects) => deleteKeyBoxFromTracklet(objects, box, objectId));
  };

  const getKeyBoxLeftPosition = (frameIndex: VideoItemBBox["frame_index"]) => {
    const boxFrameIndex = frameIndex > $lastFrameIndex ? $lastFrameIndex : frameIndex;
    return (boxFrameIndex / ($lastFrameIndex + 1)) * 100;
  };

  let left = getKeyBoxLeftPosition(box.frame_index);

  const dragMe = (node: HTMLButtonElement) => {
    let moving = false;
    let startPosition: number;
    let startFrameIndex: number;
    let startOneFrameInPixel: number;
    let newFrameIndex: number | undefined;

    node.addEventListener("mousedown", (event) => {
      moving = true;
      startPosition = event.clientX;
      startFrameIndex = box.frame_index;
      startOneFrameInPixel = oneFrameInPixel;
      selectedTool.set(panTool);
    });

    window.addEventListener("mousemove", (event) => {
      if (moving) {
        const distance = event.clientX - startPosition;
        const raise = distance / startOneFrameInPixel;
        newFrameIndex = startFrameIndex + raise;
        newFrameIndex = Math.round(newFrameIndex);
        left = getKeyBoxLeftPosition(newFrameIndex);
        updateTrackletWidth(Math.round(newFrameIndex), box.frame_index);
      }
    });

    window.addEventListener("mouseup", () => {
      moving = false;
      if (newFrameIndex !== undefined) filterTracklet(newFrameIndex, box.frame_index);
      newFrameIndex = undefined;
    });
  };
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn(
      "w-4 h-4 block bg-white border-2 rounded-full absolute left-[-0.5rem] top-1/2 translate-y-[-50%] translate-x-[-50%]",
      "hover:scale-150",
      { "bg-primary !border-primary": isBoxBeingEdited },
    )}
    style={`left: ${left}%; border-color: ${color}`}
  >
    <button class="h-full w-full" use:dragMe />
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    <ContextMenu.Item inset on:click={() => onDeleteKeyBoxClick(box)}
      >Remove key box</ContextMenu.Item
    >
    {#if !isBoxBeingEdited}
      <ContextMenu.Item inset on:click={() => onEditKeyBoxClick(box)}>Edit box</ContextMenu.Item>
    {/if}
  </ContextMenu.Content>
</ContextMenu.Root>
