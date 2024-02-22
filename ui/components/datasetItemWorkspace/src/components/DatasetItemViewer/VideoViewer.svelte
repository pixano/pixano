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
  import { onMount } from "svelte";
  import * as ort from "onnxruntime-web";
  import { PlayIcon, PauseIcon } from "lucide-svelte";

  import type { DatasetItem, SelectionTool } from "@pixano/core";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import { Canvas2D } from "@pixano/canvas2d";
  import { newShape, itemBboxes, itemMasks } from "../../lib/stores/datasetItemWorkspaceStores";

  const imageFiles = import.meta.glob("../../assets/videos/mock/*.png") || {};

  interface ImageModule {
    default: string;
  }

  export let selectedItem: DatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let selectedTool: SelectionTool;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;

  let currentImageIndex = 0;
  let intervalId: number;
  let currentImageUrl: string;
  let videoSpeed = 100;
  let views = selectedItem.views;
  let isLoaded = false;
  let currentTime: string;

  const videoTotalLengthInMs = Object.keys(imageFiles).length * videoSpeed;
  const all100ms = [...Array(Math.floor(videoTotalLengthInMs / 100)).keys()];

  onMount(async () => {
    currentImageUrl = await getCurrentImage(currentImageIndex);
    updateViews();
    isLoaded = true;
  });

  const getCurrentImage = async (index: number) => {
    try {
      const image = await Object.values(imageFiles)[index]();
      const typedImage = image as ImageModule;
      return typedImage.default;
    } catch (e) {
      return "";
    }
  };

  const updateViews = () => {
    views = {
      ...selectedItem.views,
      image: {
        ...selectedItem.views.image,
        uri: currentImageUrl || selectedItem.views.image.uri,
      },
    };
  };

  const playVideo = () => {
    if (!isLoaded) return;
    clearInterval(intervalId);
    const interval = setInterval(async () => {
      currentImageIndex = (currentImageIndex + 1) % Object.keys(imageFiles).length;
      currentImageUrl = await getCurrentImage(currentImageIndex);
      updateViews();
    }, videoSpeed);
    intervalId = Number(interval);
  };

  $: {
    const currentTimestamp = currentImageIndex * videoSpeed;
    const minutes = Math.floor(currentTimestamp / 60000);
    const seconds = ((currentTimestamp % 60000) / 1000).toFixed(0);
    currentTime = `${minutes}:${Number(seconds) < 10 ? "0" : ""}${seconds}`;
  }

  const dragMe = (node: HTMLButtonElement) => {
    let moving = false;
    let left = node.offsetLeft;

    node.addEventListener("mousedown", () => {
      console.log("mousedown");
      moving = true;
      clearInterval(intervalId);
    });

    window.addEventListener("mousemove", async (event) => {
      if (moving) {
        left = event.clientX - (node.parentElement?.offsetLeft || 0);
        if (left < 0) left = 0;
        const max = node.parentElement?.offsetWidth || left;
        if (left > max) left = max;
        node.style.left = `${left}px`;
        const index = Math.floor((left / max) * Object.keys(imageFiles).length) - 1;
        currentImageIndex = index < 0 ? 0 : index;
        currentImageUrl = await getCurrentImage(currentImageIndex);
        updateViews();
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
    const distance = event.clientX - targetElement.offsetLeft;
    currentImageIndex = Math.floor(
      (distance / targetElement.offsetWidth) * Object.keys(imageFiles).length,
    );
    currentImageUrl = await getCurrentImage(currentImageIndex);
    updateViews();
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
  <div class="pl-4 w-full flex flex-col h-full">
    {#if currentImageUrl}
      <Canvas2D
        selectedItemId={selectedItem.id}
        {views}
        colorRange={[]}
        bboxes={$itemBboxes}
        masks={$itemMasks}
        {embeddings}
        bind:selectedTool
        bind:currentAnn
        bind:newShape={$newShape}
      />
    {/if}

    <div class="bg-white flex gap-4 h-full">
      <div class="h-10 flex w-full border-b border-slate-200">
        <div class="flex justify-between w-1/3 p-2 items-center border-r border-slate-200">
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
        <div class="px-4 w-full">
          <div
            class="flex justify-between relative border-b border-slate-200 pt-8"
            role="slider"
            tabindex="0"
            on:click={onPlayerClick}
            on:keydown={onPlayerClick}
            aria-valuenow={currentImageIndex}
          >
            <button
              use:dragMe
              class="h-6 w-1 bg-primary absolute z-10 bottom-0"
              style={`left: ${((currentImageIndex * videoSpeed) / videoTotalLengthInMs) * 100}%`}
            />
            {#each all100ms as ms}
              {#if ms % 10 === 0 && ms > 0}
                <span
                  class="absolute translate-x-[-50%] text-slate-300 w-[1px] h-2 bg-slate-300 bottom-0"
                  style={`left: ${(((ms + 1) * 100) / videoTotalLengthInMs) * 100}%`}
                />
                <span
                  class="absolute translate-x-[-50%] text-slate-300 bottom-2"
                  style={`left: ${(((ms + 1) * 100) / videoTotalLengthInMs) * 100}%`}
                  >{ms / 10}s</span
                >
              {:else}
                <span
                  class="absolute translate-x-[-50%] text-slate-300 w-[1px] h-1 bg-slate-300 bottom-0"
                  style={`left: ${(((ms + 1) * 100) / videoTotalLengthInMs) * 100}%`}
                />
              {/if}
            {/each}
            <!-- <span>{videoTotalLengthInMs / 1000}</span> -->
          </div>
        </div>
      </div>
    </div>
  </div>
{/if}
