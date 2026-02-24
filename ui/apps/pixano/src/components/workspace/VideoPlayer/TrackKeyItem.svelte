<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">

  // Imports
  import type { TrackTimelineEntry } from "$lib/ui";
  import { ContextMenu, Track, cn, isLuminanceHigh } from "$lib/ui";
  import { onDeleteTrackItemClick } from "$lib/utils/entityMutations";
  import { annotations } from "$lib/stores/workspaceStores.svelte";
  import { currentFrameIndex, lastFrameIndex } from "$lib/stores/videoStores.svelte";


  interface Props {
    trackId: string;
    itemFrameIndex: number;
    track: Track;
    color: string;
    height: number;
    top: number;
    oneFrameInPixel: number;
    onEditKeyItemClick: (
    frameIndex: TrackTimelineEntry["frame_index"],
    viewname: string,
  ) => void;
    onClick: (button: number, clientX: number) => void;
    updateTrackWidth: (
    newIndex: TrackTimelineEntry["frame_index"],
    draggedIndex: TrackTimelineEntry["frame_index"],
  ) => void;
    canContinueDragging: (
    newIndex: TrackTimelineEntry["frame_index"],
    draggedIndex: TrackTimelineEntry["frame_index"],
  ) => boolean;
    resetTool: () => void;
  }

  let {
    trackId,
    itemFrameIndex,
    track: videoTrack,
    color,
    height,
    top,
    oneFrameInPixel,
    onEditKeyItemClick,
    onClick,
    updateTrackWidth,
    canContinueDragging,
    resetTool
  }: Props = $props();

  let isItemBeingEdited = $derived(
    annotations.value.filter(
      (ann) =>
        ann.ui.displayControl.editing &&
        (videoTrack.ui.childs ?? []).includes(ann) &&
        ann.ui.frame_index === itemFrameIndex &&
        ann.ui.frame_index === currentFrameIndex.value &&
        ann.data.entity_id === trackId,
    ).length === 1,
  );

  export const getKeyItemLeftPosition = (frameIndex: number) => {
    const itemFrame = frameIndex > lastFrameIndex.value ? lastFrameIndex.value : frameIndex;
    const leftPosition = (itemFrame / (lastFrameIndex.value + 1)) * 100;
    return leftPosition;
  };

  let left = $state(0);

  $effect(() => {
    left = getKeyItemLeftPosition(itemFrameIndex);
  });

  const dragMe = (node: HTMLButtonElement) => {
    if (
      !videoTrack.ui.childs?.length ||
      (videoTrack.ui.childs[0].ui.frame_index !== itemFrameIndex &&
      videoTrack.ui.childs[videoTrack.ui.childs.length - 1].ui.frame_index !== itemFrameIndex)
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
            if (newFrameIndex < 0 || newFrameIndex > lastFrameIndex.value) return;
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
            if (newFrameIndex > lastFrameIndex.value) newFrameIndex = lastFrameIndex.value;
            updateTrackWidth(newFrameIndex, itemFrameIndex);
          }
          newFrameIndex = undefined;
          dragController.abort();
        },
        { signal: dragController.signal },
      );
    });
  };

  function getDotColor(): string {
    return isLuminanceHigh(color) ? "border-border" : "border-border";
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
      aria-label="Track keyframe handle"
      style={`background-color: ${color}`}
      use:dragMe
      onclick={(e) => onClick(e.button, e.clientX)}
></button>
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    {#if videoTrack.ui.childs?.length > 2}
      <ContextMenu.Item
        onclick={() => onDeleteTrackItemClick(videoTrack, itemFrameIndex)}
        title="Remove all shapes under this key. For selective delete, use Objects panel."
      >
        Remove item
      </ContextMenu.Item>
    {/if}
    {#if !isItemBeingEdited}
      <ContextMenu.Item
        onclick={() => onEditKeyItemClick(itemFrameIndex, videoTrack.data.view_name)}
      >
        Edit item
      </ContextMenu.Item>
    {/if}
  </ContextMenu.Content>
</ContextMenu.Root>
