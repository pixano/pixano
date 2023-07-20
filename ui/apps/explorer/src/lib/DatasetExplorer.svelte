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

  import { Histogram, Table } from "@pixano/core";

  import { currentPage } from "../stores";
  import { getDatasetItems, getDatasetStats } from "./api";

  // Exports
  export let dataset = null;

  // Page navigation
  let itemsPerPage: number = 100;
  let datasetStats = null;
  let datasetItems = null;
  let featureNames;
  let curPage: number;

  currentPage.subscribe((value) => {
    curPage = value;
  });

  const dispatch = createEventDispatcher();

  function handleItemClick(event: CustomEvent) {
    dispatch("itemclick", { id: event.detail.id });
  }

  async function handleGoToFirstPage() {
    if (curPage > 1) {
      currentPage.update((n) => 1);
      datasetItems = null;
      datasetItems = await getDatasetItems(dataset.id, curPage, itemsPerPage);
    }
  }

  async function handleGoToPreviousPage() {
    if (curPage > 1) {
      currentPage.update((n) => n - 1);
      datasetItems = null;
      datasetItems = await getDatasetItems(dataset.id, curPage, itemsPerPage);
    }
  }

  async function handleGoToNextPage() {
    if (datasetItems.total > curPage * itemsPerPage) {
      currentPage.update((n) => n + 1);
      datasetItems = null;
      datasetItems = await getDatasetItems(dataset.id, curPage, itemsPerPage);
    }
  }

  async function handleGoToLastPage() {
    if (datasetItems.total > curPage * itemsPerPage) {
      currentPage.update((n) => Math.ceil(datasetItems.total / itemsPerPage));
      datasetItems = null;
      datasetItems = await getDatasetItems(dataset.id, curPage, itemsPerPage);
    }
  }

  onMount(async () => {
    datasetItems = await getDatasetItems(dataset.id, curPage, itemsPerPage);
    featureNames = datasetItems.items[0].map((c) => {
      return { name: c.name, type: c.dtype };
    });

    datasetStats = await getDatasetStats(dataset.id);
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
        <div class=" h-[85vh] w-full max-w-7xl">
          <Table
            features={datasetItems.items}
            {featureNames}
            on:itemclick={handleItemClick}
          />
        </div>

        <!-- Page navigation -->
        <div
          class="flex justify-end items-center w-full max-w-7xl space-x-2 p-4"
        >
          <span class="mr-2">
            {1 + itemsPerPage * (curPage - 1)} - {Math.min(
              itemsPerPage * curPage,
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
