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
  import pixanoLogoWhite from "./assets/pixano_white.png";
  import { svg_filter, svg_search } from "./icons";

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

<header class="w-full h-56 px-60 flex flex-col justify-evenly bg-main z-10">
  <!-- Logo & app name -->
  <button class="flex w-max space-x-6">
    <img src={pixanoLogoWhite} alt="Logo Pixano" class="w-10" />
    <span class="text-3xl font-bold text-slate-50 uppercase font-Montserrat">
      Pixano {app}
    </span>
  </button>
  <!-- Infos -->
  <div class="flex flex-row text-slate-50">
    <div class="py-5 px-8 border-2 rounded-lg border-secondary">
      <span class="text-5xl"> {datasets.length} </span>
      <span class="ml-2 text-2xl"> datasets </span>
    </div>
    <div class="ml-8 py-5 px-8 border-2 rounded-lg border-secondary">
      <span class="text-5xl">
        {datasets.reduce((sum, dataset) => sum + dataset.num_elements, 0)}
      </span>
      <span class="ml-2 text-2xl"> items </span>
    </div>
    <div class="grow flex flex-row justify-end items-end">
      <div class="flex items-center space-x-2">
        <button>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="h-10 w-10 p-2 rounded-full hover:bg-secondary"
          >
            <path d={svg_filter} fill="currentcolor" />
          </svg>
        </button>
        <div class="relative flex items-center">
          <input
            id="search-input"
            type="text"
            placeholder="Search"
            class="h-10 pl-10 pr-4 rounded border-2 accent-main text-black font-medium"
            on:input={handleSearch}
          />
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="absolute left-3 h-5 w-5 pointer-events-none"
          >
            <path d={svg_search} />
          </svg>
        </div>
      </div>
    </div>
  </div>
</header>
<div class="flex bg-slate-100 py-10">
  {#if datasets.length != 0}
    <div class="flex flex-wrap justify-center gap-6 mx-20">
      {#each datasets as dataset}
        {#if dataset.name.toUpperCase().includes(filter.toUpperCase())}
          <DatasetPreviewCard {dataset} on:selectDataset={() => handleSelectDataset(dataset)} />
        {/if}
      {/each}
    </div>
  {:else}
    <div class="mt-4 py-8 flex w-full justify-center text-lg text-slate-500">
      <span style="text-align: center;">
        No datasets found in this directory. <br /> <br />
        Please refer to
        <u>
          <a
            href="https://github.com/pixano/pixano/tree/main/notebooks/datasets/import_dataset.ipynb"
            target="_blank"
            class="text-main hover:text-secondary"
          >
            this Jupyter notebook
          </a>
        </u>
        for information on how to import your datasets.
      </span>
    </div>
  {/if}
</div>
