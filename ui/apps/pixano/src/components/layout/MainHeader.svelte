<script lang="ts">
  /// <reference types="svelte" />
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

  import { svg_search } from "@pixano/core/src/icons";
  import pixanoLogoWhite from "@pixano/core/src/assets/pixano_white.png";

  import type { DatasetInfo } from "@pixano/core/src/lib/types/datasetTypes";
  import { datasetsStore } from "$lib/stores/datasetStores";

  export let datasets: Array<DatasetInfo>;

  const handleSearch = (e: Event) => {
    const target = e.currentTarget as HTMLInputElement;
    datasetsStore.update((value = []) =>
      value.map((dataset) => ({
        ...dataset,
        isFiltered: !dataset.name.toLocaleLowerCase().includes(target.value.toLocaleLowerCase()),
      })),
    );
  };
</script>

<header class="p-4 w-full h-fit pt-10 px-20 xl:px-60 flex flex-col justify-evenly bg-primary z-10">
  <div class="flex gap-2">
    <img src={pixanoLogoWhite} alt="Logo Pixano" class="w-10 h-10" />
    <span class="text-3xl font-bold text-slate-50 uppercase"> Pixano </span>
  </div>
  <div class="flex py-5 h-40 w-full items-center flex-wrap text-slate-50">
    {#if datasets}
      <div class="h-20 my-5 mr-10 p-5 border-2 rounded-lg border-secondary">
        <span class="text-3xl"> {datasets?.length} </span>
        <span class="ml-2 text-xl"> datasets </span>
      </div>
      <div class="h-20 my-5 mr-10 p-5 border-2 rounded-lg border-secondary">
        <span class="text-3xl">
          {datasets.reduce((sum, dataset) => sum + dataset.num_elements, 0)}
        </span>
        <span class="ml-2 text-xl"> items </span>
      </div>
      <div class="grow flex flex-row justify-end items-end">
        <div class="flex items-center space-x-2">
          <div class="h-20 relative flex items-center">
            <input
              id="search-input"
              type="text"
              placeholder="Search datasets"
              class="h-10 pl-10 pr-4 rounded-full border-2 accent-main border-main text-slate-800 placeholder-slate-500 font-medium"
              on:input={handleSearch}
            />
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="48"
              viewBox="0 -960 960 960"
              width="48"
              class="absolute left-3 h-5 w-5 pointer-events-none text-slate-500"
            >
              <path d={svg_search} fill="currentcolor" />
            </svg>
          </div>
        </div>
      </div>
    {/if}
  </div>
</header>
