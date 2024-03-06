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

  import { getImageIndexFromMouseMove } from "../../lib/api/videoApi";

  export let updateView: (imageIndex: number) => void;
  export let intervalId: number;
  export let imageFilesLength: number;
  export let videoSpeed: number;
  export let currentImageIndex: number;
  export let cursorElement: HTMLButtonElement;
  export let zoomLevel: number[];

  const videoTotalLengthInMs = imageFilesLength * videoSpeed;
  let timeScaleInMs = [...Array(Math.floor(videoTotalLengthInMs / 100)).keys()];

  const dragMe = (node: HTMLButtonElement) => {
    let moving = false;

    node.addEventListener("mousedown", () => {
      moving = true;
      clearInterval(intervalId);
    });

    window.addEventListener("mousemove", (event) => {
      if (moving) {
        currentImageIndex = getImageIndexFromMouseMove(event, node, imageFilesLength);
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
    currentImageIndex = Math.floor((event.offsetX / targetElement.offsetWidth) * imageFilesLength);
    updateView(currentImageIndex);
  };
</script>

<div
  class="py-2 flex w-full h-full justify-between relative cursor-pointer bg-white"
  style={`width: ${zoomLevel[0]}%`}
  role="slider"
  tabindex="0"
  on:click={onPlayerClick}
  on:keydown={onPlayerClick}
  aria-valuenow={currentImageIndex}
>
  <span class="bg-slate-200 w-full h-[1px] absolute top-2/3" />
  <button
    use:dragMe
    class="h-8 w-1 absolute z-10 bottom-1/3 flex flex-col translate-x-[-4px]"
    style={`left: ${((currentImageIndex * videoSpeed) / videoTotalLengthInMs) * 100}%`}
    bind:this={cursorElement}
  >
    <span class="block h-[60%] bg-primary w-2 rounded-t" />
    <span
      class="block w-0 h-0 border-l-[4px] border-l-transparent border-t-[8px] border-t-primary border-r-[4px] border-r-transparent"
    >
    </span>
    <span class="w-[1px] bg-primary absolute ml-1" />
    <span class="w-[1px] bg-slate-300 h-[400px] absolute top-full ml-1" />
  </button>
  {#each timeScaleInMs as ms}
    {#if ms % 10 === 0}
      <span
        class="absolute translate-x-[-50%] text-slate-300 w-[1px] h-1 bg-slate-500 bottom-1/3 pointer-events-none"
        style={`left: ${((ms * 100) / videoTotalLengthInMs) * 100}%`}
      />
      {#if ms > 0}
        <span
          class="absolute translate-x-[-50%] text-slate-300 bottom-1/3 pointer-events-none font-light text-xs"
          style={`left: ${((ms * 100) / videoTotalLengthInMs) * 100}%`}>{ms / 10}s</span
        >
      {/if}
    {:else}
      <span
        class="absolute translate-x-[-50%] text-slate-300 w-[1px] h-1 bg-slate-300 bottom-1/3 pointer-events-none"
        style={`left: ${((ms * 100) / videoTotalLengthInMs) * 100}%`}
      />
    {/if}
  {/each}
</div>
