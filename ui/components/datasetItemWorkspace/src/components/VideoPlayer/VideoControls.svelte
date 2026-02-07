<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { PauseIcon, PlayIcon, StepBack, StepForward } from "lucide-svelte";
  import { onDestroy } from "svelte";

  import { getCurrentImageTime, updateView } from "../../lib/api/videoApi";
  import {
    currentFrameIndex,
    lastFrameIndex,
    videoControls,
  } from "../../lib/stores/videoViewerStores";

  export let resetHighlight: () => void;

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
      if ($currentFrameIndex === 0) {
        clearInterval($videoControls.intervalId);
        videoControls.update((old) => ({ ...old, intervalId: 0 }));
      }
    }, $videoControls.videoSpeed);
    videoControls.update((old) => ({ ...old, intervalId: Number(interval) }));
  };

  $: currentTime = getCurrentImageTime($currentFrameIndex, $videoControls.videoSpeed);

  const onPlayStepClick = () => {
    resetHighlight();
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
    resetHighlight();
    if ($videoControls.intervalId) {
      clearInterval($videoControls.intervalId);
      videoControls.update((old) => ({ ...old, intervalId: 0 }));
    } else {
      if (!$videoControls.isLoaded) return;
      clearInterval($videoControls.intervalId);
      currentFrameIndex.update((index) => {
        if (index === 0) return $lastFrameIndex;
        else return (index - 1) % ($lastFrameIndex + 1);
      });
      updateView($currentFrameIndex);
    }
  };

  const onPlayClick = () => {
    resetHighlight();
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

    switch (event.code) {
      case "Space":
        if (event.repeat) break;
        event.preventDefault();
        onPlayClick();
        break;
      case "ArrowRight":
      case "KeyD":
        if (event.shiftKey) break;
        onPlayStepClick();
        break;
      case "ArrowLeft":
      case "KeyA":
        if (event.shiftKey) break;
        onPlayStepBackClick();
        break;
    }
  }
</script>

<div class="bg-card flex justify-between items-center gap-4 p-4 border-b border-border w-fit">
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
    title="Previous frame (Left / A or Q)"
    on:click={onPlayStepBackClick}
    class="text-primary"
  >
    <StepBack />
  </button>
  <button title="Next frame (Right / D)" on:click={onPlayStepClick} class="text-primary">
    <StepForward />
  </button>
  <p>
    <span>{currentTime}</span>
    <span class="text-muted-foreground">({$currentFrameIndex})</span>
  </p>
</div>
<svelte:window on:keydown={shortcutHandler} />
