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

  // Imports
  import { createEventDispatcher } from "svelte";

  // Exports
  export let dataset: any;
  export let btn_label: string;

  const dispatch = createEventDispatcher();

  function handleClick() {
    dispatch("click");
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<div
  class="w-64 h-80 m-4 flex flex-col bg-zinc-50 text-zinc-900 border border-zinc-300 rounded-md cursor-pointer transition-all
  hover:scale-110
  dark:bg-zinc-800 dark:text-zinc-50 dark:border-zinc-700"
  on:click={handleClick}
>
  <!-- Dataset Infos -->
  <div class="h-1/5 px-4 flex flex-col justify-center">
    <div class="group">
      <h3 class="text-lg font-heavy truncate text-zinc-900 dark:text-zinc-300">
        {dataset.name}
      </h3>
      <!-- on Hover -->
      <div
        class="absolute h-1/5 px-4 py-0 flex flex-col justify-center hidden group-hover:block"
      >
        <div class="px-2 py-1 text-zinc-700 text-sm rounded bg-zinc-50 border">
          <p>{dataset.name}</p>
          <br />
          <i>{dataset.description}</i>
        </div>
      </div>
    </div>

    <p class="text-sm text-zinc-500">
      {dataset.num_elements} elements
    </p>
  </div>

  <!-- Dataset Thumbnail -->
  <div
    class="h-3/5 border-t border-b border-zinc-200
    dark:border-zinc-700"
  >
    <img
      src={dataset.preview}
      alt={dataset.name}
      class="h-full w-full object-cover object-center"
    />
  </div>

  <!-- Actions -->
  <div class="h-1/5 px-4 flex flex-col justify-center items-end text-sm">
    <button
      on:click={handleClick}
      class="py-2 px-3 bg-rose-500 text-zinc-50 font-heavy rounded-md border-2 border-rose-500 transition-all
      hover:text-rose-600 hover:bg-zinc-50
      dark:bg-rose-800 dark:border-rose-800
      dark:hover:text-rose-700 dark:hover:bg-zinc-800"
    >
      {btn_label}
    </button>
  </div>
</div>
