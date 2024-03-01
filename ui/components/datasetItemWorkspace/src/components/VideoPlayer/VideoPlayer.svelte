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
  import { getCurrentImageTime, getImageIndexFromMouseMove } from "../../lib/api/videoApi";
  import ObjectsTimescale from "./ObjectsTimescale.svelte";

  const imageFiles = import.meta.glob("../../assets/videos/mock/*.png") || {};

  export let updateView: (imageIndex: number) => void;

  let currentImageIndex = 0;
  let intervalId: number;
  let videoSpeed = 100;
  let isLoaded = false;
  let currentTime: string;
  let cursorElement: HTMLButtonElement;
  let zoomLevel: number[] = [0];

  const videoTotalLengthInMs = Object.keys(imageFiles).length * videoSpeed;
  let timeScaleInMs = [...Array(Math.floor(videoTotalLengthInMs / 100)).keys()];

  onMount(() => {
    updateView(currentImageIndex);
    isLoaded = true;
  });

  onDestroy(() => {
    clearInterval(intervalId);
  });

  const playVideo = () => {
    if (!isLoaded) return;
    clearInterval(intervalId);
    const interval = setInterval(() => {
      currentImageIndex = (currentImageIndex + 1) % Object.keys(imageFiles).length;
      cursorElement.scrollIntoView({ block: "nearest", inline: "center" });
      updateView(currentImageIndex);
    }, videoSpeed);
    intervalId = Number(interval);
  };

  $: currentTime = getCurrentImageTime(currentImageIndex, videoSpeed);

  const dragMe = (node: HTMLButtonElement) => {
    let moving = false;

    node.addEventListener("mousedown", () => {
      moving = true;
      clearInterval(intervalId);
    });

    window.addEventListener("mousemove", (event) => {
      if (moving) {
        currentImageIndex = getImageIndexFromMouseMove(event, node, Object.keys(imageFiles).length);
        updateView(currentImageIndex);
      }
    });

    window.addEventListener("mouseup", () => {
      moving = false;
    });
  };

  const onPlayerClick = (event: MouseEvent | KeyboardEvent) => {
    let targetElement = event.target as HTMLElement;
    if (event instanceof KeyboardEvent || targetElement.localName === "button") return;
    clearInterval(intervalId);
    currentImageIndex = Math.floor(
      (event.offsetX / targetElement.offsetWidth) * Object.keys(imageFiles).length,
    );
    updateView(currentImageIndex);
  };

  const onPlayClick = () => {
    if (intervalId) {
      clearInterval(intervalId);
      intervalId = 0;
    } else {
      playVideo();
    }
  };

  const lastImageIndex = Object.keys(imageFiles).length - 1;
  $: console.log({ objects: $itemObjects, lastImageIndex });
</script>

{#if isLoaded}
  <div class="h-full bg-white grid grid-cols-[25%_1fr] overflow-x-auto">
    <!-- top section -->
    <div class="flex justify-between items-center gap-4 p-4 sticky top-0 left-0 bg-white z-20">
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
    <div class="p-2 w-full border-b border-slate-200 sticky top-0 bg-white z-10">
      <div
        class="flex w-full justify-between relative border-b border-slate-200 pt-8 cursor-pointer"
        style={`width: ${zoomLevel[0]}%`}
        role="slider"
        tabindex="0"
        on:click={onPlayerClick}
        on:keydown={onPlayerClick}
        aria-valuenow={currentImageIndex}
      >
        <button
          use:dragMe
          class="h-8 w-1 absolute z-10 bottom-0 flex flex-col translate-x-[-4px]"
          style={`left: ${((currentImageIndex * videoSpeed) / videoTotalLengthInMs) * 100}%`}
          bind:this={cursorElement}
        >
          <span class="block h-[60%] bg-primary w-2 rounded-t" />
          <span
            class="block w-0 h-0 border-l-[4px] border-l-transparent border-t-[8px] border-t-primary border-r-[4px] border-r-transparent"
          >
          </span>
          <span class="w-[1px] bg-primary absolute ml-1" />
        </button>
        {#each timeScaleInMs as ms}
          {#if ms % 10 === 0}
            <span
              class="absolute translate-x-[-50%] text-slate-300 w-[1px] h-1 bg-slate-500 bottom-0 pointer-events-none"
              style={`left: ${((ms * 100) / videoTotalLengthInMs) * 100}%`}
            />
            {#if ms > 0}
              <span
                class="absolute translate-x-[-50%] text-slate-300 bottom-1 pointer-events-none font-light text-xs"
                style={`left: ${((ms * 100) / videoTotalLengthInMs) * 100}%`}>{ms / 10}s</span
              >
            {/if}
          {:else}
            <span
              class="absolute translate-x-[-50%] text-slate-300 w-[1px] h-1 bg-slate-300 bottom-0 pointer-events-none"
              style={`left: ${((ms * 100) / videoTotalLengthInMs) * 100}%`}
            />
          {/if}
        {/each}
      </div>
    </div>
    <!-- bottom section -->
    <div class="grow flex flex-col max-h-[150px] gap-2 col-span-2">
      {#each Object.values($itemObjects) as object}
        <ObjectsTimescale
          {videoSpeed}
          {zoomLevel}
          {object}
          {videoTotalLengthInMs}
          {lastImageIndex}
        />
      {/each}
    </div>
  </div>
{/if}
