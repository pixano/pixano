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

  import { createEventDispatcher } from "svelte";

  export let dataset: any;
  const dispatch = createEventDispatcher();

  function handleClick() {
    dispatch("click");
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<div class="w-80 flex flex-col shadow rounded-sm">
  <!-- Dataset Infos -->
  <div class="px-8 pt-6 pb-4 flex flex-col justify-center font-semibold">
    <h3 class="text-lg mb-2">
      {dataset.name}
    </h3>
    <p class="text-xs text-slate-400">
      {dataset.num_elements} items
    </p>
  </div>

  <!-- Dataset Thumbnail -->
  <div class="grid grid-cols-4 gap-[1px]">
    {#each dataset.previews as img}
      <img
        src={img}
        alt="img preview"
        class="h-20 w-20 object-cover object-center"
      />
    {/each}
  </div>

  <!-- Actions -->
  <div class="px-4 py-6 flex justify-end items-center space-x-3">
    <button
      class="py-2 px-4 bg-rose-900 text-zinc-50 font-medium rounded-md transition-all hover:bg-rose-800"
    >
      Explore
    </button>
    <button
      on:click={handleClick}
      class="py-2 px-4 bg-rose-900 text-zinc-50 font-medium rounded-md transition-all hover:bg-rose-800"
    >
      Annotate
    </button>
  </div>
</div>
