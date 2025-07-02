<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { TrackletItem } from "@pixano/core";
  import { cn, ContextMenu, Tracklet } from "@pixano/core";

  import { isLuminanceHigh } from "../../../../core/src/lib/utils/colorUtils";
  import { onDeleteItemClick } from "../../lib/api/objectsApi";
  import { annotations } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex, lastFrameIndex } from "../../lib/stores/videoViewerStores";

  export let trackId: string;

  export let itemFrameIndex: number;
  export let tracklet: Tracklet;
  export let color: string;
  export let height: number;
  export let top: number;
  export let oneFrameInPixel: number;
  export let onEditKeyItemClick: (
    frameIndex: TrackletItem["frame_index"],
    viewname: string,
  ) => void;
  export let onClick: (button: number, clientX: number) => void;
  export let updateTrackletWidth: (
    newIndex: TrackletItem["frame_index"],
    draggedIndex: TrackletItem["frame_index"],
  ) => void;
  export let canContinueDragging: (
    newIndex: TrackletItem["frame_index"],
    draggedIndex: TrackletItem["frame_index"],
  ) => boolean;
  export let resetTool: () => void;

  let isItemBeingEdited = false;

  $: {
    const currentObjectsBeingEdited = $annotations.filter(
      (ann) =>
        ann.ui.displayControl.editing &&
        tracklet.ui.childs.includes(ann) &&
        ann.ui.frame_index === itemFrameIndex &&
        ann.ui.frame_index === $currentFrameIndex &&
        ann.data.entity_ref.id === trackId,
    );
    isItemBeingEdited = currentObjectsBeingEdited.length === 1;
  }

  export const getKeyItemLeftPosition = (frameIndex: number) => {
    const itemFrameIndex = frameIndex > $lastFrameIndex ? $lastFrameIndex : frameIndex;
    const leftPosition = (itemFrameIndex / ($lastFrameIndex + 1)) * 100;
    return leftPosition;
  };

  let left = getKeyItemLeftPosition(itemFrameIndex);

  const dragMe = (node: HTMLButtonElement) => {
    if (
      tracklet.ui.childs[0].ui.frame_index !== itemFrameIndex &&
      tracklet.ui.childs[tracklet.ui.childs.length - 1].ui.frame_index !== itemFrameIndex
    )
      return;

    let moving = false;
    let startPosition: number;
    let startFrameIndex: number;
    let startOneFrameInPixel: number;
    let newFrameIndex: number | undefined;

    node.addEventListener("mousedown", (event) => {
      moving = true;
      startPosition = event.clientX;
      startFrameIndex = itemFrameIndex;
      startOneFrameInPixel = oneFrameInPixel;
      resetTool();
      const dragController = new AbortController();

      window.addEventListener(
        "mousemove",
        (event) => {
          if (moving) {
            const distance = event.clientX - startPosition;
            const raise = distance / startOneFrameInPixel;
            newFrameIndex = Math.round(startFrameIndex + raise);
            if (newFrameIndex < 0 || newFrameIndex > $lastFrameIndex) return;
            const canContinue = canContinueDragging(newFrameIndex, itemFrameIndex);
            if (canContinue) {
              left = getKeyItemLeftPosition(newFrameIndex);
            }
          }
        },
        { signal: dragController.signal },
      );

      window.addEventListener(
        "mouseup",
        () => {
          moving = false;
          if (newFrameIndex !== undefined) {
            if (newFrameIndex < 0) newFrameIndex = 0;
            if (newFrameIndex > $lastFrameIndex) newFrameIndex = $lastFrameIndex;
            updateTrackletWidth(newFrameIndex, itemFrameIndex);
          }
          newFrameIndex = undefined;
          dragController.abort();
        },
        { signal: dragController.signal },
      );
    });
  };

  function getDotColor(): string {
    return isLuminanceHigh(color) ? "border-slate-500" : "border-slate-300";
  }
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn(
      "w-2 z-50 block border-2 rounded-full absolute left-[-0.5rem] translate-x-[-50%]",
      "hover:scale-150 ",
      isItemBeingEdited ? "bg-primary !border-primary" : getDotColor(),
    )}
    style={`left: ${left}%; top: ${top + height * 0.125}%; height: ${height * 0.75}%; background-color: ${color};`}
  >
    <button
      class="w-full h-full rounded-full absolute"
      style={`background-color: ${color}`}
      use:dragMe
      on:click={(e) => onClick(e.button, e.clientX)}
    />
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    {#if tracklet.ui.childs?.length > 2}
      <ContextMenu.Item
        on:click={() => onDeleteItemClick(tracklet, itemFrameIndex)}
        title="Remove all shapes under this key. For selective delete, use Objects panel."
      >
        Remove item
      </ContextMenu.Item>
    {/if}
    {#if !isItemBeingEdited}
      <ContextMenu.Item
        on:click={() => onEditKeyItemClick(itemFrameIndex, tracklet.data.view_ref.name)}
      >
        Edit item
      </ContextMenu.Item>
    {/if}
  </ContextMenu.Content>
</ContextMenu.Root>
