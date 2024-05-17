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
  import { itemObjects } from "../../lib/stores/datasetItemWorkspaceStores";
  import {
    currentFrameIndex,
    itemBoxBeingEdited,
    lastFrameIndex,
  } from "../../lib/stores/videoViewerStores";
  import { deleteKeyBoxFromTracklet } from "../../lib/api/videoApi";

  export let objectId: ItemObject["id"];

  export let keyBox: VideoItemBBox;
  export let isBeingEdited: boolean;
  export let color: string;
  export let oneFrameInPixel: number;
  export let onEditKeyBoxClick: (keyBox: VideoItemBBox) => void;
  export let updateTrackletWidth: (
    newIndex: VideoItemBBox["frame_index"],
    draggedIndex: VideoItemBBox["frame_index"],
  ) => void;

  $itemBoxBeingEdited?.objectId === objectId &&
    keyBox.frame_index === $itemBoxBeingEdited?.frame_index;

  const onDeleteKeyBoxClick = (box: VideoItemBBox) => {
    itemObjects.update((objects) => deleteKeyBoxFromTracklet(objects, box, objectId));
  };

  const getKeyBoxLeftPosition = (box: VideoItemBBox) => {
    const boxFrameIndex = box.frame_index > $lastFrameIndex ? $lastFrameIndex : box.frame_index;
    return (boxFrameIndex / ($lastFrameIndex + 1)) * 100;
  };

  const dragMe = (node: HTMLButtonElement) => {
    let moving = false;
    let startPosition: number;
    let startFrameIndex: number;
    let startOneFrameInPixel: number;

    node.addEventListener("mousedown", (event) => {
      moving = true;
      startPosition = event.clientX;
      startFrameIndex = keyBox.frame_index;
      startOneFrameInPixel = oneFrameInPixel;
    });

    window.addEventListener("mousemove", (event) => {
      if (moving && isBeingEdited) {
        const distance = event.clientX - startPosition;
        const raise = distance / startOneFrameInPixel;
        const newFrameIndex = startFrameIndex + raise;
        // currentFrameIndex.set(Math.round(newFrameIndex));
        updateTrackletWidth(Math.round(newFrameIndex), keyBox.frame_index);
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
      { "bg-primary !border-primary": keyBox.frame_index === $currentFrameIndex },
    )}
    style={`left: ${getKeyBoxLeftPosition(keyBox)}%; border-color: ${color}`}
  >
    <button class="h-full w-full" use:dragMe />
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    <ContextMenu.Item inset on:click={() => onDeleteKeyBoxClick(keyBox)}
      >Remove key box</ContextMenu.Item
    >
    <ContextMenu.Item inset on:click={() => onEditKeyBoxClick(keyBox)}>
      {isBeingEdited ? "Stop editing" : "Edit box"}
    </ContextMenu.Item>
  </ContextMenu.Content>
</ContextMenu.Root>
