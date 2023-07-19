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
  class="w-64 h-80 m-4 flex flex-col rounded-md cursor-pointer transition-all hover:scale-110
  border border-zinc-300 dark:border-zinc-500"
  on:click={handleClick}
>
  <!-- Dataset Infos -->
  <div class="h-1/5 px-4 flex flex-col justify-center">
    <div class="group">
      <h3
        class="text-lg font-heavy truncate"
        title="{dataset.name} - {dataset.description}"
      >
        {dataset.name}
      </h3>
    </div>

    <p class="text-sm text-zinc-600 dark:text-zinc-400">
      {dataset.num_elements} elements
    </p>
  </div>

  <!-- Dataset Thumbnail -->
  <div class="h-3/5">
    <img
      src={dataset.preview}
      alt=""
      class="h-full w-full object-cover object-center"
    />
  </div>

  <!-- Actions -->
  <div class="h-1/5 px-4 flex flex-col justify-center items-end text-sm">
    <button
      on:click={handleClick}
      class="py-2 px-3 border border-transparent font-heavy rounded-md transition-all
      text-zinc-50
      bg-rose-500 dark:bg-rose-600
      hover:bg-rose-600 dark:hover:bg-rose-500"
    >
      {btn_label}
    </button>
  </div>
</div>
