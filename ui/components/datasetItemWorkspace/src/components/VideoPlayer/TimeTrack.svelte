<script lang="ts">
  import { onMount } from "svelte";
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

  import { getImageIndexFromMouseMove } from "../../lib/api/videoApi";
  import {
    lastFrameIndex,
    currentFrameIndex,
    videoControls,
  } from "../../lib/stores/videoViewerStores";
  import { selectedTool } from "../../lib/stores/datasetItemWorkspaceStores";
  import { panTool } from "../../lib/settings/selectionTools";

  export let updateView: (imageIndex: number) => void;

  let cursorElement: HTMLButtonElement;
  let timeTrackElement: HTMLElement;

  let timeTrackElement: HTMLElement;

  let imageFilesLength = $lastFrameIndex + 1;
  const videoTotalLengthInMs = imageFilesLength * $videoControls.videoSpeed;
  let timeScaleInMs = [...Array(Math.floor(videoTotalLengthInMs / 100)).keys()];
  let timeTrackDensity = 1;

  const changeSelectedTool = () => {
    if ($selectedTool.name !== panTool.name) {
      selectedTool.set(panTool);
    }
  };

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
        changeSelectedTool();
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
    if (event instanceof KeyboardEvent || targetElement.localName === "button") return;
    clearInterval($videoControls.intervalId);
    $videoControls.intervalId = 0;
    currentFrameIndex.set(
      Math.floor((event.offsetX / targetElement.offsetWidth) * imageFilesLength),
    );
    updateView($currentFrameIndex);
    changeSelectedTool();
  };

  const shouldDisplayTime = (ms: number, density: number) => {
    if (ms % 10 !== 0) return false;
    if (50 < density && ms % 50 === 0) return true;
    if (25 < density && density < 50 && ms % 20 === 0) return true;
    if (density < 25) return true;
    return false;
  };

  $: {
    if ($videoControls.zoomLevel[0]) {
      updateTimeTrack();
    }
  }

  const shouldDisplayMarker = (ms: number, density: number) => {
    if (density > 200) return false;
    if (density > 25 && ms % 10 === 0) return true;
    if (density < 25) return true;
    return false;
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
          class="absolute -translate-x-1/2 text-slate-300 bottom-1/3 pointer-events-none font-light text-xs pb-1"
          style={`left: ${((ms * 100) / videoTotalLengthInMs) * 100}%`}>{ms / 10}s</span
        >
      {/if}
    {:else if shouldDisplayMarker(ms, timeTrackDensity)}
      <span
        class="absolute text-slate-300 w-[1px] h-1 bg-slate-300 bottom-1/3 pointer-events-none"
        style={`left: ${((ms * 100) / videoTotalLengthInMs) * 100}%`}
      />
    {/if}
  {/each}
</div>
