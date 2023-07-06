<script lang="ts">
  /**
  @copyright CEA-LIST/DIASI/SIALV/LVA (2023)
  @author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
  @license CECILL-C

  This software is a collaborative computer program whose purpose is to
  generate and explore labeled data for computer vision applications.
  This software is governed by the CeCILL-C license under French law and
  abiding by the rules of distribution of free software. You can use, 
  modify and/ or redistribute the software under the terms of the CeCILL-C
  license as circulated by CEA, CNRS and INRIA at the following URL

  http://www.cecill.info
  */

  import { onMount } from "svelte";
  import { createEventDispatcher } from "svelte";
  import { ImageDetails } from "@pixano/core";
  import { getItemDetails } from "./api";

  export let datasetId;
  export let rowIndex;

  let features = null;

  const dispatch = createEventDispatcher();

  function handleCloseClick() {
    dispatch("closeclick");
  }

  async function handleKeyDown(e) {
    if (e.keyCode == 27) handleCloseClick(); // Escape key pressed
  }

  onMount(async () => {
    features = await getItemDetails(datasetId, rowIndex);
  });
</script>

<div class="absolute top-0 bg-white w-screen h-screen dark:bg-zinc-900">
  {#if features}
    <ImageDetails {features} />
  {/if}

  <!-- Close button -->
  <button class="absolute top-0 right-0 p-2 z-10" on:click={handleCloseClick}>
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="28"
      height="28"
      viewBox="0 0 28 28"
      class=" fill-rose-600 hover:fill-rose-400"
    >
      <path
        class="transition-colors"
        d="M12 10.59l4.95-4.95c0.39-0.39 1.02-0.39 1.41 0l1.41 1.41c0.39 0.39 0.39 1.02 0 1.41l-4.95 4.95l4.95 4.95c0.39 0.39 0.39 1.02 0 1.41l-1.41 1.41c-0.39 0.39-1.02 0.39-1.41 0l-4.95-4.95l-4.95 4.95c-0.39 0.39-1.02 0.39-1.41 0l-1.41-1.41c-0.39-0.39-0.39-1.02 0-1.41l4.95-4.95l-4.95-4.95c-0.39-0.39-0.39-1.02 0-1.41l1.41-1.41c0.39-0.39 1.02-0.39 1.41 0l4.95 4.95z"
      />
    </svg>
  </button>
</div>
<!-- Pixano Explorer footer -->
<div
  class="absolute bottom-0 right-0 px-2 py-1 bg-zinc-50 text-zinc-500 text-sm border-t border-l rounded-tl-lg
  dark:bg-zinc-900 dark:text-zinc-300 dark:border-zinc-500"
>
  Pixano Explorer
</div>

<svelte:window on:keydown={handleKeyDown} />
