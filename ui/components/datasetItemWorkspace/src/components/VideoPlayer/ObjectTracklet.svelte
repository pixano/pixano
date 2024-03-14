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
  import type { Tracklet, VideoObject, VideoItemBBox } from "@pixano/core";
  import { itemBoxBeingEdited, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import TrackletKeyBox from "./TrackletKeyBox.svelte";

  export let object: VideoObject;
  export let color: string;
  export let tracklet: Tracklet;
  export let onContextMenu: (event: MouseEvent) => void;
  export let onEditKeyBoxClick: (box: VideoItemBBox) => void;
  export let onAddKeyBoxClick: () => void;
  export let findNeighborKeyBoxes: (tracklet: Tracklet, frameIndex: number) => [number, number];

  const getLeft = (tracklet: Tracklet) => (tracklet.start / ($lastFrameIndex + 1)) * 100;
  const getWidth = (tracklet: Tracklet) => {
    const end = tracklet.end > $lastFrameIndex ? $lastFrameIndex : tracklet.end;
    return ((end - tracklet.start) / ($lastFrameIndex + 1)) * 100;
  };

  let width: number = getWidth(tracklet);
  let left: number = getLeft(tracklet);
  let trackletElement: HTMLElement;

  $: width = getWidth(tracklet);
  $: left = getLeft(tracklet);
  $: oneFrameInPixel =
    trackletElement?.getBoundingClientRect().width / (tracklet.end - tracklet.start + 1);

  const updateTrackletWidth = (
    newFrameIndex: VideoItemBBox["frameIndex"],
    draggedFrameIndex: VideoItemBBox["frameIndex"],
  ) => {
    const [prevFrameIndex, nextFrameIndex] = findNeighborKeyBoxes(tracklet, draggedFrameIndex);
    if (newFrameIndex <= prevFrameIndex || newFrameIndex >= nextFrameIndex) return;
    tracklet.keyBoxes = tracklet.keyBoxes.map((keyBox) => {
      if (keyBox.frameIndex === draggedFrameIndex) {
        keyBox.frameIndex = newFrameIndex;
        itemBoxBeingEdited.set({
          ...keyBox,
          objectId: object.id,
        });
      }
      return keyBox;
    });
    tracklet.start = tracklet.keyBoxes[0].frameIndex;
    tracklet.end = tracklet.keyBoxes[tracklet.keyBoxes.length - 1].frameIndex;
  };

  const isKeyBoxBeingEdited = (keyBox: VideoItemBBox) =>
    $itemBoxBeingEdited?.objectId === object.id &&
    keyBox.frameIndex === $itemBoxBeingEdited?.frameIndex;
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn("h-4/5 w-full absolute top-1/2 -translate-y-1/2")}
    style={`left: ${left}%; width: ${width}%; background-color: ${color}`}
  >
    <button
      on:contextmenu|preventDefault={(e) => onContextMenu(e)}
      class="h-full w-full"
      bind:this={trackletElement}
    />
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    <ContextMenu.Item inset on:click={onAddKeyBoxClick}>Add a point</ContextMenu.Item>
  </ContextMenu.Content>
</ContextMenu.Root>
{#each tracklet.keyBoxes as keyBox}
  <TrackletKeyBox
    {keyBox}
    {color}
    isBeingEdited={isKeyBoxBeingEdited(keyBox)}
    {onEditKeyBoxClick}
    objectId={object.id}
    {updateTrackletWidth}
    {oneFrameInPixel}
  />
{/each}
