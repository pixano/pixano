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
  import DatasetPreviewCard from "./DatasetPreviewCard.svelte";
  import pixanoLogo from "./assets/pixano.png";

  // Exports
  export let datasets: Array<Dataset>;
  export let app: string = "";

  let filter = "";

  const dispatch = createEventDispatcher();

  function handleSelectDataset(dataset: Dataset) {
    dispatch("selectDataset", dataset);
  }

  function handleSearch() {
    filter = (document.getElementById("search-input") as HTMLInputElement).value;
  }
</script>

<header class="w-full h-56 px-60 flex flex-col justify-evenly bg-[#771E5F] z-10">
  <!-- Logo & app name -->
  <button class="flex w-max space-x-6">
    <img src={pixanoLogo} alt="Logo Pixano" class="w-10" />
    <span class="text-3xl font-bold text-white uppercase font-[Montserrat]"> Pixano {app} </span>
  </button>
  <!-- Infos -->
  <div class="flex flex-row text-white">
    <div class="py-6 px-8 border-2 rounded-lg border-[#872E6F]">
      <span class="text-5xl"> {datasets.length} </span> <span class="ml-2 text-2xl"> datasets </span>
    </div>
    <div class="ml-8 py-6 px-8 border-2 rounded-lg border-[#872E6F]">
      <span class="text-5xl"> {datasets.reduce((sum, dataset) => sum + dataset.num_elements, 0)} </span>
      <span class="ml-2 text-2xl"> items </span>
    </div>
    <div class="grow flex flex-row justify-end items-end">
      <input
        id="search-input"
        type="text"
        placeholder="Search"
        class="h-10 px-4 rounded border-2 border-[#872E6F] text-black font-medium"
        on:input={handleSearch}
      />
    </div>
  </div>
</header>
<div class="py-8 flex">
  {#if datasets.length != 0}
    <div class="w-full mx-60">
      <div class="grid grid-cols-3 gap-6">
        {#each datasets as dataset}
          {#if dataset.name.toUpperCase().includes(filter.toUpperCase())}
            <DatasetPreviewCard {dataset} on:selectDataset={() => handleSelectDataset(dataset)} />
          {/if}
        {/each}
      </div>
    </div>
  {:else}
    <div class="mt-4 py-8 flex w-full justify-center text-lg text-zinc-500 dark:text-zinc-300">
      <span style="text-align: center;">
        No datasets found in this directory. <br /> <br />
        Please refer to
        <u>
          <a
            href="https://github.com/pixano/pixano/tree/main/notebooks/datasets/import_dataset.ipynb"
            target="_blank"
            class="text-rose-500 dark:text-rose-600
          hover:text-rose-600 dark:hover:text-rose-500"
          >
            this Jupyter notebook
          </a>
        </u>
        for information on how to import your datasets.
      </span>
    </div>
  {/if}
</div>
