<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onMount } from "svelte";

  import { getImageIndexFromMouseMove } from "../../lib/api/videoApi";
  import {
    currentFrameIndex,
    lastFrameIndex,
    videoControls,
  } from "../../lib/stores/videoViewerStores";

  export let updateView: (imageIndex: number) => void;
  export let resetTool: () => void;

  let cursorElement: HTMLButtonElement;
  let timeTrackElement: HTMLElement;

  let imageFilesLength = $lastFrameIndex + 1;
  const videoTotalLengthInMs = imageFilesLength * $videoControls.videoSpeed;
  let timeScaleInMs = [...Array(Math.floor(videoTotalLengthInMs / 100)).keys()];
  let timeTrackDensity = 1;

  const dragMe = (node: HTMLButtonElement) => {
    let moving = false;

    node.addEventListener("mousedown", () => {
      moving = true;
      clearInterval($videoControls.intervalId);
    });

    window.addEventListener("mousemove", (event) => {
      if (moving) {
        currentFrameIndex.set(getImageIndexFromMouseMove(event, node, imageFilesLength));
        updateView($currentFrameIndex);
        resetTool();
      }
    });

    window.addEventListener("mouseup", () => {
      moving = false;
    });
  };

  const updateTimeTrack = () => {
    if (!timeTrackElement) return;
    const boundRect = timeTrackElement.getBoundingClientRect();
    const width = boundRect.width;
    timeTrackDensity = videoTotalLengthInMs / width;
  };

  onMount(() => {
    updateTimeTrack();
  });

  const onPlayerClick = (event: MouseEvent | KeyboardEvent) => {
    let targetElement = event.target as HTMLElement;
    if (
      event instanceof KeyboardEvent ||
      targetElement.localName === "button" ||
      targetElement instanceof HTMLSpanElement
    )
      return;
    clearInterval($videoControls.intervalId);
    $videoControls.intervalId = 0;
    currentFrameIndex.set(
      Math.round((event.offsetX / targetElement.offsetWidth) * imageFilesLength),
    );
    updateView($currentFrameIndex);
    resetTool();
  };

  const shouldDisplayTime = (ms: number, density: number) => {
    let densityThresholds = [2000, 1000, 500, 400, 250, 100, 50, 25];
    let displayedTimes = [1200, 600, 300, 200, 150, 100, 50, 20];
    for (let i = 0; i < densityThresholds.length; ++i) {
      if (density > densityThresholds[i]) {
        return ms % displayedTimes[i] === 0;
      }
    }
    return ms % 10 === 0;
  };

  $: {
    if ($videoControls.zoomLevel[0]) {
      updateTimeTrack();
    }
  }

  const shouldDisplayMarker = (ms: number, density: number) => {
    let densityThresholds = [2000, 1000, 500, 400, 250, 20, 10];
    let displayedMarkers = [600, 300, 150, 100, 50, 10, 5];
    for (let i = 0; i < densityThresholds.length; ++i) {
      if (density > densityThresholds[i]) {
        return ms % displayedMarkers[i] === 0;
      }
    }
    return true;
  };
</script>

<div
  class="py-2 flex w-full h-16 justify-between relative cursor-pointer bg-white border-b border-slate-200 focus:outline-none"
  style={`width: ${$videoControls.zoomLevel[0]}%`}
  role="slider"
  tabindex="0"
  on:click={onPlayerClick}
  on:keydown={onPlayerClick}
  aria-valuenow={$currentFrameIndex}
  bind:this={timeTrackElement}
>
  <span class="bg-slate-200 w-full h-[1px] absolute top-2/3" />
  <button
    use:dragMe
    class="h-8 w-1 absolute bottom-1/3 flex flex-col translate-x-[-4px]"
    style={`left: ${(($currentFrameIndex * $videoControls.videoSpeed) / videoTotalLengthInMs) * 100}%`}
    bind:this={cursorElement}
  >
    <span class="block h-[60%] bg-primary w-2 rounded-t" />
    <span
      class="block w-0 h-0 border-l-[4px] border-l-transparent border-t-[8px] border-t-primary border-r-[4px] border-r-transparent"
    ></span>
    <span class="w-[1px] bg-primary absolute ml-1" />
    <span class="w-[1px] bg-primary h-5 absolute top-full ml-1" />
  </button>
  {#each timeScaleInMs as ms}
    {#if shouldDisplayTime(ms, timeTrackDensity)}
      <span
        class="absolute text-slate-300 w-[1px] h-1 bg-slate-500 bottom-1/3 pointer-events-none"
        style={`left: ${((ms * 100) / videoTotalLengthInMs) * 100}%`}
      />
      {#if ms > 0}
        <span
          class="absolute -translate-x-1/2 text-slate-500 bottom-1/3 pointer-events-none font-light text-xs pb-1"
          style={`left: ${((ms * 100) / videoTotalLengthInMs) * 100}%`}
        >
          {#if videoTotalLengthInMs > 60000}
            {Math.floor(ms / 600)}:{String(Math.floor(ms % 600) / 10).padStart(2, "0")}
          {:else}
            {Math.floor(ms % 600) / 10}s
          {/if}
        </span>
      {/if}
    {:else if shouldDisplayMarker(ms, timeTrackDensity)}
      <span
        class="absolute text-slate-300 w-[1px] h-1 bg-slate-300 bottom-1/3 pointer-events-none"
        style={`left: ${((ms * 100) / videoTotalLengthInMs) * 100}%`}
      />
    {/if}
  {/each}
</div>
