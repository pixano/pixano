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

  import { itemObjects } from "../../lib/stores/datasetItemWorkspaceStores";

  import ObjectTrack from "./ObjectTrack.svelte";
  import TimeTrack from "./TimeTrack.svelte";
  import VideoPlayerRow from "./VideoPlayerRow.svelte";
  import VideoControls from "./VideoControls.svelte";

  import {
    currentFrameIndex,
    lastFrameIndex,
    videoControls,
  } from "../../lib/stores/videoViewerStores";
  import { SliderRoot } from "@pixano/core";
  import { onMount } from "svelte";

  export let updateView: (frameIndex: number) => void;

  onMount(() => {
    updateView($currentFrameIndex);
    videoControls.update((old) => ({ ...old, isLoaded: true }));
  });

  const onTimeTrackClick = (index: number) => {
    currentFrameIndex.set(index);
    updateView($currentFrameIndex);
  };

  itemObjects.subscribe((value) => {
    const highlightedObject = value.find((item) => item.highlighted === "self");
    if (!highlightedObject) return;
    const element = document.querySelector(`#video-object-${highlightedObject.id}`);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });
</script>

{#if $videoControls.isLoaded}
  <div class="h-full bg-white overflow-x-auto relative flex flex-col">
    <div class="sticky top-0 bg-white z-20">
      <VideoPlayerRow class="bg-white ">
        <TimeTrack slot="timeTrack" {updateView} />
      </VideoPlayerRow>
    </div>
    <div class="flex flex-col grow z-10">
      {#each Object.values($itemObjects) as object}
        {#if object.datasetItemType === "video"}
          <VideoPlayerRow>
            <ObjectTrack slot="timeTrack" {object} {onTimeTrackClick} {updateView} />
          </VideoPlayerRow>
        {/if}
      {/each}
    </div>
    <div class="px-2 sticky bottom-0 left-0 z-20 bg-white shadow flex justify-between">
      <VideoControls {updateView} />
      <SliderRoot
        class="max-w-[200px]"
        bind:value={$videoControls.zoomLevel}
        min={100}
        max={$lastFrameIndex * 3}
      />
    </div>
  </div>
{/if}
