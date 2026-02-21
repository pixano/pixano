<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { PauseIcon, PlayIcon, StepBack, StepForward } from "lucide-svelte";
  import { getCurrentImageTime } from "$lib/utils/videoUtils";
  import { updateView } from "$lib/utils/videoOperations";
  import {
    currentFrameIndex,
    lastFrameIndex,
    videoControls,
  } from "$lib/stores/videoStores.svelte";

  interface Props {
    resetHighlight: () => void;
  }

  let { resetHighlight }: Props = $props();

  let currentTime: string = $derived(getCurrentImageTime(currentFrameIndex.value, videoControls.value.videoSpeed));

  $effect(() => {
    return () => clearInterval(videoControls.value.intervalId);
  });

  const playVideo = () => {
    if (!videoControls.value.isLoaded) return;
    clearInterval(videoControls.value.intervalId);
    const interval = setInterval(() => {
      currentFrameIndex.update((index) => (index + 1) % (lastFrameIndex.value + 1));
      updateView(currentFrameIndex.value);
      if (currentFrameIndex.value === 0) {
        clearInterval(videoControls.value.intervalId);
        videoControls.update((old) => ({ ...old, intervalId: 0 }));
      }
    }, videoControls.value.videoSpeed);
    videoControls.update((old) => ({ ...old, intervalId: Number(interval) }));
  };

  

  const onPlayStepClick = () => {
    resetHighlight();
    if (videoControls.value.intervalId) {
      clearInterval(videoControls.value.intervalId);
      videoControls.update((old) => ({ ...old, intervalId: 0 }));
    } else {
      if (!videoControls.value.isLoaded) return;
      clearInterval(videoControls.value.intervalId);
      currentFrameIndex.update((index) => (index + 1) % (lastFrameIndex.value + 1));
      updateView(currentFrameIndex.value);
    }
  };

  const onPlayStepBackClick = () => {
    resetHighlight();
    if (videoControls.value.intervalId) {
      clearInterval(videoControls.value.intervalId);
      videoControls.update((old) => ({ ...old, intervalId: 0 }));
    } else {
      if (!videoControls.value.isLoaded) return;
      clearInterval(videoControls.value.intervalId);
      currentFrameIndex.update((index) => {
        if (index === 0) return lastFrameIndex.value;
        else return (index - 1) % (lastFrameIndex.value + 1);
      });
      updateView(currentFrameIndex.value);
    }
  };

  const onPlayClick = () => {
    resetHighlight();
    if (videoControls.value.intervalId) {
      clearInterval(videoControls.value.intervalId);
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
    title={videoControls.value.intervalId ? "Pause (space)" : "Play (space)"}
    onclick={onPlayClick}
    class="text-primary"
  >
    {#if videoControls.value.intervalId}
      <PauseIcon />
    {:else}
      <PlayIcon />
    {/if}
  </button>
  <button
    title="Previous frame (Left / A or Q)"
    onclick={onPlayStepBackClick}
    class="text-primary"
  >
    <StepBack />
  </button>
  <button title="Next frame (Right / D)" onclick={onPlayStepClick} class="text-primary">
    <StepForward />
  </button>
  <p>
    <span>{currentTime}</span>
    <span class="text-muted-foreground">({currentFrameIndex.value})</span>
  </p>
</div>
<svelte:window onkeydown={shortcutHandler} />
