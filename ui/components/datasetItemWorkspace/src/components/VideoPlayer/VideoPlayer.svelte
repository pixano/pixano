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
  import { getCurrentImageTime, getImageIndexFromMouseMove } from "../../lib/api/videoApi";

  const imageFiles = import.meta.glob("../../assets/videos/mock/*.png") || {};

  interface ImageModule {
    default: string;
  }

  export let updateViews: (imageUrl: string) => void;

  let currentImageIndex = 0;
  let intervalId: number;
  let currentImageUrl: string;
  let videoSpeed = 100;
  let isLoaded = false;
  let currentTime: string;
  let cursorElement: HTMLButtonElement;
  let zoomLevel: number[] = [0];

  const videoTotalLengthInMs = Object.keys(imageFiles).length * videoSpeed;
  let timeScaleInMs = [...Array(Math.floor(videoTotalLengthInMs / 100)).keys()];

  const updateCurrentImage = async (index: number) => {
    try {
      const image = await Object.values(imageFiles)[index]();
      const typedImage = image as ImageModule;
      currentImageUrl = typedImage.default;
      updateViews(currentImageUrl);
    } catch (e) {
      return new Error("Error while updating current image");
    }
  };

  onMount(async () => {
    await updateCurrentImage(currentImageIndex);
    isLoaded = true;
  });

  onDestroy(() => {
    clearInterval(intervalId);
  });

  const playVideo = () => {
    if (!isLoaded) return;
    clearInterval(intervalId);
    const interval = setInterval(async () => {
      currentImageIndex = (currentImageIndex + 1) % Object.keys(imageFiles).length;
      cursorElement.scrollIntoView({ block: "nearest", inline: "center" });
      await updateCurrentImage(currentImageIndex);
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

    window.addEventListener("mousemove", async (event) => {
      if (moving) {
        currentImageIndex = getImageIndexFromMouseMove(event, node, Object.keys(imageFiles).length);
        await updateCurrentImage(currentImageIndex);
      }
    });

    window.addEventListener("mouseup", () => {
      moving = false;
    });
  };

  const onPlayerClick = async (event: MouseEvent | KeyboardEvent) => {
    let targetElement = event.target as HTMLElement;
    if (event instanceof KeyboardEvent || targetElement.localName === "button") return;
    clearInterval(intervalId);
    currentImageIndex = Math.floor(
      (event.offsetX / targetElement.offsetWidth) * Object.keys(imageFiles).length,
    );
    await updateCurrentImage(currentImageIndex);
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
  <div class="bg-white flex h-full">
    <!-- left section -->
    <div class="w-1/4 min-w-[25%] border-r border-slate-200">
      <div class="h-12 flex justify-between p-2 items-center">
        <p>
          {currentTime}
        </p>
        <button on:click={onPlayClick} class="text-primary">
          {#if intervalId}
            <PauseIcon />
          {:else}
            <PlayIcon />
          {/if}
        </button>
      </div>
      <div class="flex gap-2 flex-col p-4">
        <SliderRoot bind:value={zoomLevel} min={100} max={200} />
      </div>
    </div>
    <!-- right section -->
    <div class="h-32 p-2 w-full border-b border-slate-200 overflow-x-auto overflow-y-hidden">
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
          <span class="h-32 w-[1px] bg-primary absolute ml-1" />
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
  </div>
{/if}
