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
  let videoSpeed = 300;
  let views = selectedItem.views;
  let isLoaded = false;
  let currentTime: string;

  const videoTotalLengthInMs = Object.keys(imageFiles).length * videoSpeed;
  const allSec = [...Array(Math.floor(videoTotalLengthInMs / 1000)).keys()];

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
      currentImageIndex = currentImageIndex + 1;
      currentImageUrl = await getCurrentImage(currentImageIndex);
      updateViews();
    }, videoSpeed);
    intervalId = Number(interval);
  };

  const stopVideo = () => {
    clearInterval(intervalId);
  };

  $: {
    const currentTimestamp = currentImageIndex * videoSpeed;
    const minutes = Math.floor(currentTimestamp / 60000);
    const seconds = ((currentTimestamp % 60000) / 1000).toFixed(0);
    currentTime = `${minutes}:${Number(seconds) < 10 ? "0" : ""}${seconds}`;
  }

  function dragMe(node: HTMLButtonElement) {
    let moving = false;
    let left = node.offsetLeft;

    node.style.left = `${left}px`;

    node.addEventListener("mousedown", () => {
      moving = true;
      clearInterval(intervalId);
    });

    window.addEventListener("mousemove", async (e) => {
      if (moving) {
        left += e.movementX;
        if (left < 0) left = 0;
        const max = node.parentElement?.offsetWidth || left;
        if (left > max) left = max;
        node.style.left = `${left}px`;
        currentImageIndex = Math.floor((left / max) * Object.keys(imageFiles).length);
        currentImageUrl = await getCurrentImage(currentImageIndex);
        updateViews();
      }
    });

    window.addEventListener("mouseup", () => {
      moving = false;
    });
  }
</script>

{#if isLoaded}
  <div class="bg-white p-5 w-full">
    <div class="">
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
    </div>
    <div class="bg-white flex gap-4">
      <button on:click={playVideo}>play</button>
      <button on:click={stopVideo}>pause</button>
      <p>{currentTime}</p>
      <div class="w-full flex justify-between bg-red-500 relative">
        <button
          use:dragMe
          class="h-full w-2 bg-slate-900 absolute z-10"
          style={`left: ${((currentImageIndex * videoSpeed) / videoTotalLengthInMs) * 100}%`}
        />
        <span>0</span>
        {#each allSec as sec}
          <span
            class="absolute bg-green-500 translate-x-[-50%]"
            style={`left: ${(((sec + 1) * 1000) / videoTotalLengthInMs) * 100}%`}>{sec + 1}</span
          >
        {/each}
        <span>{videoTotalLengthInMs / 1000}</span>
      </div>
    </div>
  </div>
{/if}
