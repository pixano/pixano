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
  import { createEventDispatcher, onMount } from "svelte";

  import { api, Histogram, Table } from "@pixano/core";

  import type { DatasetItems } from "@pixano/core";

  // Exports
  export let selectedDataset = null;
  export let currentPage: number;

  // Page navigation
  let itemsPerPage: number = 100;
  let datasetStats = null;
  let datasetItems: DatasetItems = null;

  const dispatch = createEventDispatcher();

  function handleSelectItem(event: CustomEvent) {
    dispatch("selectItem", { id: event.detail.id });
  }

  async function loadPage() {
    datasetItems = null;
    const start = Date.now();
    datasetItems = await api.getDatasetItems(
      selectedDataset.id,
      currentPage,
      itemsPerPage
    );
    console.log(
      "DatasetExplorer.loadPage - api.getDatasetItems in",
      Date.now() - start,
      "ms"
    );
  }

  async function handleGoToFirstPage() {
    if (currentPage > 1) {
      currentPage = 1;
      loadPage();
    }
  }

  async function handleGoToPreviousPage() {
    if (currentPage > 1) {
      currentPage -= 1;
      loadPage();
    }
  }

  async function handleGoToNextPage() {
    if (datasetItems.total > currentPage * itemsPerPage) {
      currentPage += 1;
      loadPage();
    }
  }

  async function handleGoToLastPage() {
    if (datasetItems.total > currentPage * itemsPerPage) {
      currentPage = Math.ceil(datasetItems.total / itemsPerPage);
      loadPage();
    }
  }

  onMount(async () => {
    datasetItems = await api.getDatasetItems(
      selectedDataset.id,
      currentPage,
      itemsPerPage
    );
    datasetStats = await api.getDatasetStats(selectedDataset.id);
  });
</script>

<div class="mt-4 px-2">
  <div class="flex">
    <!-- Stats -->
    <div
      class="w-1/2 h-[85vh] flex flex-col items-center border rounded-lg overflow-y-scroll max-w-5xl
      border-zinc-300 dark:border-zinc-500"
    >
      <span class="font-bold text-xl mt-3"> Stats </span>
      {#if datasetStats != null && datasetStats.length != 0}
        <div class="grid grid-cols-1 2xl:grid-cols-2 w-full gap-4 p-4">
          <!-- If charts are ready to be displayed, display them -->
          {#each datasetStats as chart}
            <div class="w-full">
              <Histogram hist={chart} />
            </div>
          {/each}
        </div>
      {:else}
        <!-- Else show a message -->
        <span class="mt-80 italic text-zinc-500 dark:text-zinc-300">
          No stats available.
        </span>
      {/if}
    </div>

    <div class="w-1/2 ml-4">
      {#if datasetItems}
        <!-- Items list -->
        <div class=" h-[85vh] z-0 w-full max-w-7xl">
          <Table {datasetItems} on:selectItem={handleSelectItem} />
        </div>

        <!-- Page navigation -->
        <div
          class="flex justify-end items-center w-full max-w-7xl space-x-2 p-4"
        >
          <span class="mr-2">
            {1 + itemsPerPage * (currentPage - 1)} - {Math.min(
              itemsPerPage * currentPage,
              datasetItems.total
            )} of {datasetItems.total}
          </span>
          {#if datasetItems.total > itemsPerPage}
            <button
              class="py-1 px-2 border rounded-lg text-sm font-medium
              bg-white dark:bg-zinc-800
              hover:bg-zinc-100 dark:hover:bg-zinc-700
              border-zinc-300 dark:border-zinc-500"
              on:click={handleGoToFirstPage}
            >
              FIRST
            </button>

            <button
              class="py-1 px-2 border rounded-lg text-sm font-medium
              bg-white dark:bg-zinc-800
              hover:bg-zinc-100 dark:hover:bg-zinc-700
              border-zinc-300 dark:border-zinc-500"
              on:click={handleGoToPreviousPage}
            >
              PREV
            </button>

            <button
              class="py-1 px-2 border rounded-lg text-sm font-medium
              bg-white dark:bg-zinc-800
              hover:bg-zinc-100 dark:hover:bg-zinc-700
              border-zinc-300 dark:border-zinc-500"
              on:click={handleGoToNextPage}
            >
              NEXT
            </button>

            <button
              class="py-1 px-2 border rounded-lg text-sm font-medium
              bg-white dark:bg-zinc-800
              hover:bg-zinc-100 dark:hover:bg-zinc-700
              border-zinc-300 dark:border-zinc-500"
              on:click={handleGoToLastPage}
            >
              LAST
            </button>
          {/if}
        </div>
      {:else}
        <div class="h-full flex justify-center items-center">
          <span class="italic text-zinc-500 dark:text-zinc-300">
            Loading items...
          </span>
        </div>
      {/if}
    </div>
  </div>
</div>
