<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onDestroy } from "svelte";
  import { PlayIcon, PauseIcon } from "lucide-svelte";
  import { getCurrentImageTime } from "../../lib/api/videoApi";
  import {
    lastFrameIndex,
    currentFrameIndex,
    videoControls,
  } from "../../lib/stores/videoViewerStores";
  import { selectedTool } from "../../lib/stores/datasetItemWorkspaceStores";
  import { panTool } from "../../lib/settings/selectionTools";

  export let updateView: (frameIndex: number) => void;

  let currentTime: string;

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
    selectedTool.set(panTool);
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
