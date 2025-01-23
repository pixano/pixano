<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onDestroy } from "svelte";
  import { PlayIcon, PauseIcon, StepForward, StepBack } from "lucide-svelte";
  import { getCurrentImageTime } from "../../lib/api/videoApi";
  import {
    lastFrameIndex,
    currentFrameIndex,
    videoControls,
  } from "../../lib/stores/videoViewerStores";

  export let updateView: (frameIndex: number) => void;
  export let resetTool: () => void;

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

  const onPlayStepClick = () => {
    resetTool();
    if ($videoControls.intervalId) {
      clearInterval($videoControls.intervalId);
      videoControls.update((old) => ({ ...old, intervalId: 0 }));
    } else {
      if (!$videoControls.isLoaded) return;
      clearInterval($videoControls.intervalId);
      currentFrameIndex.update((index) => (index + 1) % ($lastFrameIndex + 1));
      updateView($currentFrameIndex);
    }
  };

  const onPlayStepBackClick = () => {
    resetTool();
    if ($videoControls.intervalId) {
      clearInterval($videoControls.intervalId);
      videoControls.update((old) => ({ ...old, intervalId: 0 }));
    } else {
      if (!$videoControls.isLoaded) return;
      clearInterval($videoControls.intervalId);
      currentFrameIndex.update((index) => {
        if (index == 0) return $lastFrameIndex;
        else return (index - 1) % ($lastFrameIndex + 1);
      });
      updateView($currentFrameIndex);
    }
  };

  const onPlayClick = () => {
    resetTool();
    if ($videoControls.intervalId) {
      clearInterval($videoControls.intervalId);
      videoControls.update((old) => ({ ...old, intervalId: 0 }));
    } else {
      playVideo();
    }
  };

  function shortcutHandler(event: KeyboardEvent) {
    const activeElement = document.activeElement;
    if (
      activeElement instanceof HTMLInputElement ||
      activeElement instanceof HTMLTextAreaElement ||
      activeElement?.getAttribute("contenteditable") === "true"
    ) {
      return; // Ignore shortcut when typing text
    }

    switch (event.key) {
      case " ":
        if (event.repeat) break;
        onPlayClick();
        break;
      case "ArrowRight":
        if (event.shiftKey) break;
        onPlayStepClick();
        break;
      case "ArrowLeft":
        if (event.shiftKey) break;
        onPlayStepBackClick();
        break;
    }
  }
</script>

<div class="bg-white flex justify-between items-center gap-4 p-4 border-b border-slate-200 w-fit">
  <button
    title={$videoControls.intervalId ? "Pause (space)" : "Play (space)"}
    on:click={onPlayClick}
    class="text-primary"
  >
    {#if $videoControls.intervalId}
      <PauseIcon />
    {:else}
      <PlayIcon />
    {/if}
  </button>
  <button
    title="One step backward (left arrow)"
    on:click={onPlayStepBackClick}
    class="text-primary"
  >
    <StepBack />
  </button>
  <button title="One step forward (right arrow)" on:click={onPlayStepClick} class="text-primary">
    <StepForward />
  </button>
  <p>
    <span>{currentTime}</span> <span class="text-gray-400">({$currentFrameIndex})</span>
  </p>
</div>
<svelte:window on:keydown={shortcutHandler} />
