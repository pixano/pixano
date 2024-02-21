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

  const imageFiles = import.meta.glob("../../assets/videos/mock/*.png");

  let currentImageIndex = 0;
  let intervalId: number;
  let currentImageUrl: string;
  let videoSpeed = 100;
  interface ImageModule {
    default: string;
  }

  const videoTotalLengthInMs = Object.keys(imageFiles).length * videoSpeed;

  const getCurrentImage = async (index: number) => {
    try {
      const image = await Object.values(imageFiles)[index]();
      const typedImage = image as ImageModule;
      return typedImage.default;
    } catch (e) {
      return "";
    }
  };

  const playVideo = () => {
    clearInterval(intervalId);
    const interval = setInterval(async () => {
      currentImageIndex = (currentImageIndex + 1) % Object.keys(imageFiles).length;
      currentImageUrl = await getCurrentImage(currentImageIndex);
    }, videoSpeed);
    intervalId = Number(interval);
  };

  const stopVideo = () => {
    clearInterval(intervalId);
  };

  let currentTime: string;
  $: {
    const currentTimestamp = currentImageIndex * videoSpeed;
    const minutes = Math.floor(currentTimestamp / 60000);
    const seconds = ((currentTimestamp % 60000) / 1000).toFixed(0);
    currentTime = `${minutes}:${Number(seconds) < 10 ? "0" : ""}${seconds}`;
  }
  const allSec = [...Array(Math.floor(videoTotalLengthInMs / 1000)).keys()];

  function dragMe(node: HTMLButtonElement) {
    // https://svelte.dev/repl/25a1141c007b4d2097367b12a559f63a?version=4.2.11
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
      }
    });

    window.addEventListener("mouseup", () => {
      moving = false;
      playVideo();
    });
  }

  onMount(async () => {
    currentImageUrl = await getCurrentImage(currentImageIndex);
  });
</script>

<div class="bg-white p-5 w-full">
  <div class="">
    {#if currentImageUrl}
      <img src={currentImageUrl} alt="video" class="w-full" />
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
