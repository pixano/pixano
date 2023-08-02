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

  // Exports
  export let dataset: any;
  export let buttonLabel: string;

  const dispatch = createEventDispatcher();

  function handleSelectDataset() {
    dispatch("selectDataset");
  }
</script>

<button
  class="w-64 h-80 m-4 flex flex-col rounded-md transition-all hover:scale-110 text-left
  shadow dark:shadow-zinc-700
  border border-zinc-300 dark:border-zinc-600"
  on:click={handleSelectDataset}
>
  <!-- Dataset Infos -->
  <div class="w-full h-1/5 px-4 flex flex-col justify-center">
    <div class="group">
      <h3
        class="text-lg font-heavy truncate"
        title="{dataset.name}&#10;&#13;{dataset.description}"
      >
        {dataset.name}
      </h3>
    </div>

    <p class="text-sm text-zinc-600 dark:text-zinc-400">
      {dataset.num_elements} elements
    </p>
  </div>

  <!-- Dataset Thumbnail -->
  <div class="h-3/5 bg-zinc-100 dark:bg-zinc-700">
    {#if dataset.preview}
      <img
        src={dataset.preview}
        alt="{dataset.name} thumbnail"
        class="h-full w-full object-cover object-center"
      />
    {/if}
  </div>

  <!-- Actions -->
  <div class="h-1/5 px-4 flex flex-col justify-center items-end text-sm">
    <button
      class="py-2 px-3 border border-transparent font-heavy rounded-md transition-all
      text-zinc-50
      bg-rose-500 dark:bg-rose-600
      hover:bg-rose-600 dark:hover:bg-rose-500"
    >
      {buttonLabel}
    </button>
  </div>
</button>
