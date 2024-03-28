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
  import type { ItemObject, KeyVideoFrame } from "@pixano/core";
  import { itemObjects } from "../../lib/stores/datasetItemWorkspaceStores";
  import { lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import { deleteKeyFrameFromTracklet } from "../../lib/api/videoApi";

  export let objectId: ItemObject["id"];

  export let keyFrame: KeyVideoFrame;
  export let isBeingEdited: boolean;
  export let color: string;
  export let oneFrameInPixel: number;
  export let onEditKeyFrameClick: (keyFrame: KeyVideoFrame) => void;
  export let updateTrackletWidth: (
    newIndex: KeyVideoFrame["frameIndex"],
    draggedIndex: KeyVideoFrame["frameIndex"],
  ) => void;

  const onDeleteKeyBoxClick = (frame: KeyVideoFrame) => {
    itemObjects.update((objects) => deleteKeyFrameFromTracklet(objects, frame, objectId));
  };

  const getKeyBoxLeftPosition = (frame: KeyVideoFrame) => {
    const boxFrameIndex = frame.frameIndex > $lastFrameIndex ? $lastFrameIndex : frame.frameIndex;
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
      startFrameIndex = keyFrame.frameIndex;
      startOneFrameInPixel = oneFrameInPixel;
    });

    window.addEventListener("mousemove", (event) => {
      if (moving && isBeingEdited) {
        const distance = event.clientX - startPosition;
        const raise = distance / startOneFrameInPixel;
        const newFrameIndex = startFrameIndex + raise;
        updateTrackletWidth(Math.round(newFrameIndex), keyFrame.frameIndex);
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
    style={`left: ${getKeyBoxLeftPosition(keyFrame)}%; border-color: ${color}`}
  >
    <button class="h-full w-full" use:dragMe />
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    <ContextMenu.Item inset on:click={() => onDeleteKeyBoxClick(keyFrame)}
      >Remove key frame</ContextMenu.Item
    >
    <ContextMenu.Item inset on:click={() => onEditKeyFrameClick(keyFrame)}>
      {isBeingEdited ? "Stop editing" : "Edit frame"}
    </ContextMenu.Item>
  </ContextMenu.Content>
</ContextMenu.Root>
