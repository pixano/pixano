<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { getImageIndexFromMouseMove } from "../../lib/api/videoApi";
  import {
    lastFrameIndex,
    currentFrameIndex,
    videoControls,
  } from "../../lib/stores/videoViewerStores";
  import { onMount } from "svelte";

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
    if (density > 2000) {
      return ms % 1200 === 0;
    } else if (density > 1000) {
      return ms % 600 === 0;
    } else if (density > 500) {
      return ms % 300 === 0;
    } else if (density > 400) {
      return ms % 200 === 0;
    } else if (density > 250) {
      return ms % 150 === 0;
    } else if (density > 100) {
      return ms % 100 === 0;
    } else if (density > 50) {
      return ms % 50 === 0;
    } else if (density > 25) {
      return ms % 20 === 0;
    } else {
      return ms % 10 === 0;
    }
  };

  $: {
    if ($videoControls.zoomLevel[0]) {
      updateTimeTrack();
    }
  }

  const shouldDisplayMarker = (ms: number, density: number) => {
    if (density > 2000) {
      return ms % 600 === 0;
    } else if (density > 1000) {
      return ms % 300 === 0;
    } else if (density > 500) {
      return ms % 150 === 0;
    } else if (density > 400) {
      return ms % 100 === 0;
    } else if (density > 250) {
      return ms % 50 === 0;
    } else if (density > 20) {
      return ms % 10 === 0;
    } else if (density > 10) {
      return ms % 5 === 0;
    } else {
      return true;
    }
  };
</script>

<div
  class="py-2 flex w-full h-16 justify-between relative cursor-pointer bg-white border-b border-slate-200"
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
    >
    </span>
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
