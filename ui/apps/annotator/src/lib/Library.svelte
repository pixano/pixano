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
  import DatasetPreviewCard from "./DatasetPreviewCard.svelte";

  export let datasets: any;

  const dispatch = createEventDispatcher();

  function handleDatasetClick(dataset) {
    dispatch("datasetclick", { dataset: dataset });
  }
</script>

<div class="relative w-full flex flex-col font-[Montserrat]">
  <div class="h-72 mx-auto flex flex-col shrink-0 justify-end">
    <img
      src={datasets[0].previews[0]}
      alt="img preview"
      class="absolute top-0 left-0 w-full h-72 object-cover brightness-50 -z-10 bg-white"
    />
    <div class="flex justify-between items-end">
      <div class="flex flex-col">
        <span class="text-3xl font-semibold text-white">
          {datasets[0].name}
        </span>
        <span class="text-sm font-semibold text-slate-400">
          {datasets[0].num_elements} items
        </span>
      </div>
      <div class="space-x-3">
        <button
          class="px-4 py-2 bg-white border border-rose-900 rounded-md text-rose-900"
        >
          Explore
        </button>
        <button
          class="px-4 py-2 bg-white border border-rose-900 rounded-md text-rose-900"
          on:click={() => handleDatasetClick(datasets[0])}
        >
          Annotate
        </button>
      </div>
    </div>
    <div class="mx-auto mb-8 mt-6 flex justify-evenly space-x-2">
      {#each datasets[0].previews.slice(1, 8) as preview}<img
          src={preview}
          alt="img preview"
          class="h-36 w-36 object-cover shrink-0 blur-[0.5px]"
        />{/each}
    </div>
  </div>

  <div class="mx-auto mt-8 pb-8">
    <select class="w-32 mb-8 px-2 py-1 bg-white border-2 rounded text-zinc-500 font-medium">
      <option value="" disabled selected>Sort by...</option>
      <option value="default">Default</option>
    </select>

    <div class="grid grid-cols-3 gap-12">
      {#each datasets.slice(1) as dataset}
        <DatasetPreviewCard
          {dataset}
          on:click={() => handleDatasetClick(dataset)}
        />
      {/each}
    </div>
  </div>
</div>
