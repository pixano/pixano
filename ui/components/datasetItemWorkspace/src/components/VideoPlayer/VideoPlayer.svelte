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
  import { onDestroy, onMount } from "svelte";
  import { PlayIcon, PauseIcon } from "lucide-svelte";

  import { SliderRoot } from "@pixano/core";
  import { itemObjects } from "../../lib/stores/datasetItemWorkspaceStores";
  import { getCurrentImageTime } from "../../lib/api/videoApi";

  import ObjectTrack from "./ObjectTrack.svelte";
  import TimeTrack from "./TimeTrack.svelte";
  import VideoPlayerRow from "./VideoPlayerRow.svelte";
  import { lastFrameIndex, currentFrameIndex } from "../../lib/stores/videoViewerStores";

  export let updateView: (frameIndex: number) => void;
  export let colorScale: (id: string) => string;

  let intervalId: number;
  let videoSpeed = 100;
  let isLoaded = false;
  let currentTime: string;
  let cursorElement: HTMLButtonElement;
  let zoomLevel: number[] = [0];

  onMount(() => {
    updateView($currentFrameIndex);
    isLoaded = true;
  });

  onDestroy(() => {
    clearInterval(intervalId);
  });

  const playVideo = () => {
    if (!isLoaded) return;
    clearInterval(intervalId);
    const interval = setInterval(() => {
      currentFrameIndex.update((index) => (index + 1) % ($lastFrameIndex + 1));
      cursorElement.scrollIntoView({ block: "nearest", inline: "center" });
      updateView($currentFrameIndex);
    }, videoSpeed);
    intervalId = Number(interval);
  };

  $: currentTime = getCurrentImageTime($currentFrameIndex, videoSpeed);

  const onTimeTrackClick = (index: number) => {
    currentFrameIndex.set(index);
    updateView($currentFrameIndex);
  };

  const onPlayClick = () => {
    if (intervalId) {
      clearInterval(intervalId);
      intervalId = 0;
    } else {
      playVideo();
    }
  };
</script>

{#if isLoaded}
  <div class="h-full bg-white overflow-x-auto">
    <!-- top section -->
    <VideoPlayerRow class="sticky top-0 bg-white z-20" isTopRow>
      <div
        slot="name"
        class="bg-white flex justify-between items-center gap-4 p-4 border-b border-slate-200"
      >
        <p>
          {currentTime}
        </p>
        <SliderRoot bind:value={zoomLevel} min={100} max={200} />
        <button on:click={onPlayClick} class="text-primary">
          {#if intervalId}
            <PauseIcon />
          {:else}
            <PlayIcon />
          {/if}
        </button>
      </div>
      <TimeTrack
        slot="timeTrack"
        {updateView}
        {videoSpeed}
        {intervalId}
        {zoomLevel}
        bind:cursorElement
      />
    </VideoPlayerRow>
    <!-- bottom section -->
    <div class="flex flex-col max-h-[150px] z-10 relative">
      {#each Object.values($itemObjects) as object}
        {#if object.datasetItemType === "video"}
          <VideoPlayerRow>
            <p slot="name" class="py-4 sticky left-0 bg-white text-ellipsis overflow-hidden p-2">
              {object.id}
            </p>
            <ObjectTrack slot="timeTrack" {zoomLevel} {object} {onTimeTrackClick} {colorScale} />
          </VideoPlayerRow>
        {/if}
      {/each}
    </div>
  </div>
{/if}
