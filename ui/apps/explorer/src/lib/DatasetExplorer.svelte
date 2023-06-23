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
  import { createEventDispatcher, onMount } from "svelte";
  import { getDatasetItems, getDatasetStats } from "./api";
  import { Table, Histogram } from "@pixano/core";
  import { currentPage } from "../stores";

  // Page navigation
  export let dataset = null;
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

  async function handleGoToPreviousPage() {
    if (curPage > 1) {
      currentPage.update((n) => n - 1);
      datasetItems = null;
      datasetItems = await getDatasetItems(dataset.id, curPage, itemsPerPage);
    } else alert("There is no previous page.");
  }

  async function handleGoToNextPage() {
    if (datasetItems.total > curPage * itemsPerPage) {
      currentPage.update((n) => n + 1);
      datasetItems = null;
      datasetItems = await getDatasetItems(dataset.id, curPage, itemsPerPage);
    } else alert("Last page reached.");
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
      class="w-1/2 h-[85vh] pr-4 flex flex-col items-center border rounded-lg overflow-y-scroll
       dark:border-zinc-700 dark:bg-zinc-800"
    >
      <span class="font-bold text-xl mt-3"> Stats </span>
      {#if datasetStats != null && datasetStats.length != 0}
        <div class="grid grid-cols-3 my-2">
          <!-- If charts are ready to be displayed, display them -->
          {#each datasetStats as chart}
            <div class="ml-2 mb-2">
              <Histogram hist={chart} />
            </div>
          {/each}
        </div>
      {:else}
        <!-- Else show a message -->
        <span class="mt-80 italic text-zinc-500">No stats available.</span>
      {/if}
    </div>

    <div class="w-1/2 ml-4">
      {#if datasetItems}
        <!-- Items list -->
        <div class=" h-[85vh] w-full mb-1">
          <Table
            features={datasetItems.items}
            {featureNames}
            on:itemclick={handleItemClick}
          />
        </div>

        <!-- Page navigation -->
        <div class="flex justify-end items-center w-full space-x-2">
          <span class="mr-2">
            {1 + itemsPerPage * (curPage - 1)} - {itemsPerPage * curPage} of {datasetItems.total}
          </span>
          <button
            class="py-1 px-2 bg-white border-2 rounded-lg text-zinc-500 text-sm font-medium
            hover:bg-zinc-100
            dark:bg-zinc-900 dark:border-zinc-800 dark:text-zinc-300
            dark:hover:bg-zinc-700"
            on:click={handleGoToPreviousPage}>PREV</button
          >
          <button
            class="py-1 px-2 bg-white border-2 rounded-lg text-zinc-500 text-sm font-medium
            hover:bg-zinc-100
            dark:bg-zinc-900 dark:border-zinc-800 dark:text-zinc-300
            dark:hover:bg-zinc-700"
            on:click={handleGoToNextPage}>NEXT</button
          >
        </div>
      {:else}
        <div class="h-full flex justify-center items-center">
          <span class="text-zinc-500 italic">Loading items ...</span>
        </div>
      {/if}
    </div>
  </div>
</div>
