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
  import type { Tracklet, VideoObject, KeyVideoFrame } from "@pixano/core";
  import { keyFrameBeingEdited, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import TrackletKeyBox from "./TrackletKeyFrame.svelte";

  export let object: VideoObject;
  export let color: string;
  export let tracklet: Tracklet;
  export let onContextMenu: (event: MouseEvent) => void;
  export let onEditKeyFrameClick: (keyFrame: KeyVideoFrame) => void;
  export let onAddKeyFrameClick: () => void;
  export let onSplitTrackletClick: () => void;
  export let onDeleteTrackletClick: () => void;
  export let findNeighborKeyFrames: (tracklet: Tracklet, frameIndex: number) => [number, number];

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
    newFrameIndex: KeyVideoFrame["frameIndex"],
    draggedFrameIndex: KeyVideoFrame["frameIndex"],
  ) => {
    const [prevFrameIndex, nextFrameIndex] = findNeighborKeyFrames(tracklet, draggedFrameIndex);
    if (newFrameIndex <= prevFrameIndex || newFrameIndex >= nextFrameIndex) return;
    tracklet.keyFrames = tracklet.keyFrames.map((keyFrame) => {
      if (keyFrame.frameIndex === draggedFrameIndex) {
        keyFrame.frameIndex = newFrameIndex;
        keyFrameBeingEdited.set({
          ...keyFrame,
          objectId: object.id,
        });
      }
      return keyFrame;
    });
    tracklet.start = tracklet.keyFrames[0].frameIndex;
    tracklet.end = tracklet.keyFrames[tracklet.keyFrames.length - 1].frameIndex;
  };

  const isKeyFrameBeingEdited = (keyFrame: KeyVideoFrame) =>
    $keyFrameBeingEdited?.objectId === object.id &&
    keyFrame.frameIndex === $keyFrameBeingEdited?.frameIndex;
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
    <ContextMenu.Item inset on:click={onAddKeyFrameClick}>Add a point</ContextMenu.Item>
    <ContextMenu.Item inset on:click={onSplitTrackletClick}>Split tracklet</ContextMenu.Item>
    <ContextMenu.Item inset on:click={onDeleteTrackletClick}>Delete tracklet</ContextMenu.Item>
  </ContextMenu.Content>
</ContextMenu.Root>
{#each tracklet.keyFrames as keyFrame}
  <TrackletKeyBox
    {keyFrame}
    {color}
    isBeingEdited={isKeyFrameBeingEdited(keyFrame)}
    {onEditKeyFrameClick}
    objectId={object.id}
    {updateTrackletWidth}
    {oneFrameInPixel}
  />
{/each}
