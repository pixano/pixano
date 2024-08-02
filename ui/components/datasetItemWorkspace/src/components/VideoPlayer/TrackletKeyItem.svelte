<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ContextMenu, cn } from "@pixano/core";
  import type { ItemObject, TrackletItem, VideoItemBBox } from "@pixano/core";
  import { itemObjects, selectedTool, canSave } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import { deleteKeyBoxFromTracklet } from "../../lib/api/videoApi";
  import { panTool } from "../../lib/settings/selectionTools";

  export let objectId: ItemObject["id"];

  export let item: TrackletItem;
  export let color: string;
  export let height: number;
  export let top: number;
  export let oneFrameInPixel: number;
  export let onEditKeyItemClick: (frameIndex: TrackletItem["frame_index"]) => void;
  export let updateTracklet: () => void;
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

  const onDeleteItemClick = () => {
    itemObjects.update((objects) => deleteKeyBoxFromTracklet(objects, item, objectId));
    //TODO ? check if deleting a key has deleted last tracklet of itemObject => delete it (?)
    updateTracklet();
    canSave.set(true);
  };

  export const getKeyItemLeftPosition = (frameIndex: VideoItemBBox["frame_index"]) => {
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
      //TODO canSave.set(true);
    });
  };
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn(
      "w-2 z-50 block border-2 border-slate-500 rounded-full absolute left-[-0.5rem] translate-x-[-50%]",
      "hover:scale-150",
      { "bg-primary !border-primary": isItemBeingEdited },
    )}
    style={`left: ${left}%; top: ${top + height * 0.125}%; height: ${height * 0.75}%; background-color: ${color}`}
  >
    <button class="h-full w-full" use:dragMe />
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    <ContextMenu.Item inset on:click={() => onDeleteItemClick()}>Remove item</ContextMenu.Item>
    {#if !isItemBeingEdited}
      <ContextMenu.Item inset on:click={() => onEditKeyItemClick(item.frame_index)}
        >Edit item</ContextMenu.Item
      >
    {/if}
  </ContextMenu.Content>
</ContextMenu.Root>
