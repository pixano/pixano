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

  // Imports
  import { createEventDispatcher } from "svelte";

  import type { Dataset } from "./interfaces";
  import { svg_right_arrow } from "./icons";

  // Exports
  export let dataset: Dataset;

  const dispatch = createEventDispatcher();

  function handleSelectDataset() {
    dispatch("selectDataset");
  }
</script>

<button
  class="w-full h-56 flex flex-col transition-all text-left
  bg-slate-50 border rounded-sm border-slate-300 shadow shadow-slate-300 hover:shadow-md"
  on:click={handleSelectDataset}
>
  <!-- Dataset Infos -->
  <div class="w-full h-2/5 px-4 flex flex-col justify-center relative">
    <div>
      <h3
        class="text-lg font-semibold font-[Montserrat] truncate text-main"
        title="{dataset.name}&#10;&#13;{dataset.description}"
      >
        {dataset.name}
      </h3>
    </div>

    <p class="text-sm text-slate-500 font-medium">
      {dataset.num_elements} items {dataset.estimated_size &&
      dataset.estimated_size != "N/A"
        ? " - " + dataset.estimated_size
        : ""}
    </p>
    <svg
      xmlns="http://www.w3.org/2000/svg"
      height="48"
      viewBox="0 -960 960 960"
      width="48"
      class="absolute right-5 h-8 w-8 mx-auto p-2 border rounded-full border-slate-300 hover:bg-slate-300"
    >
      <title>Open</title>
      <path d={svg_right_arrow} fill="currentcolor" />
    </svg>
  </div>

  <!-- Dataset Thumbnail -->
  <div class="h-3/5 mx-4 mb-4 bg-slate-100">
    {#if dataset.preview}
      <img
        src={dataset.preview}
        alt="{dataset.name} thumbnail"
        class="h-full w-full object-cover object-center"
      />
    {/if}
  </div>
  <!-- <div class="h-3/5 mx-4 mb-4 grid grid-cols-4 gap-1">
    {#each dataset.preview as preview}
      <img src={dataset.preview} alt="{dataset.name} thumbnail" class="h-full w-full rounded object-cover object-center bg-slate-100" />
    {/each}
  </div> -->
</button>
