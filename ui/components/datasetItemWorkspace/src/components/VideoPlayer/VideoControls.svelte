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
  import { getCurrentImageTime } from "../../lib/api/videoApi";
  import {
    lastFrameIndex,
    currentFrameIndex,
    videoControls,
  } from "../../lib/stores/videoViewerStores";

  export let updateView: (frameIndex: number) => void;

  let currentTime: string;

  onMount(() => {
    updateView($currentFrameIndex);
    videoControls.update((old) => ({ ...old, isLoaded: true }));
  });

  onDestroy(() => {
    clearInterval($videoControls.intervalId);
  });

  const playVideo = () => {
    if (!$videoControls.isLoaded) return;
    clearInterval($videoControls.intervalId);
    const interval = setInterval(() => {
      currentFrameIndex.update((index) => (index + 1) % ($lastFrameIndex + 1));
      updateView($currentFrameIndex);
    }, $videoControls.videoSpeed);
    videoControls.update((old) => ({ ...old, intervalId: Number(interval) }));
  };

  $: currentTime = getCurrentImageTime($currentFrameIndex, $videoControls.videoSpeed);

  const onPlayClick = () => {
    if ($videoControls.intervalId) {
      clearInterval($videoControls.intervalId);
      videoControls.update((old) => ({ ...old, intervalId: 0 }));
    } else {
      playVideo();
    }
  };
</script>

<div class="bg-white flex justify-between items-center gap-4 p-4 border-b border-slate-200 w-fit">
  <p>
    {currentTime}
  </p>
  <button on:click={onPlayClick} class="text-primary">
    {#if $videoControls.intervalId}
      <PauseIcon />
    {:else}
      <PlayIcon />
    {/if}
  </button>
</div>
