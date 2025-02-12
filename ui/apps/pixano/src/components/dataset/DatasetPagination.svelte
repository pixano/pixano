<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { DatasetBrowser } from "@pixano/core/src";

  import {
    svg_first_page,
    svg_last_page,
    svg_next_page,
    svg_prev_page,
  } from "@pixano/core/src/icons";

  import {
    DEFAULT_DATASET_TABLE_PAGE,
    DEFAULT_DATASET_TABLE_SIZE,
  } from "$lib/constants/pixanoConstants";
  import { datasetTableStore } from "../../lib/stores/datasetStores";

  // Exports
  export let selectedDataset: DatasetBrowser;
  export let isLoadingTableItems: boolean;

  // Page navigation
  let currentPage: number;
  let pageSize: number;

  datasetTableStore.subscribe((value) => {
    currentPage = value?.currentPage || DEFAULT_DATASET_TABLE_PAGE;
    pageSize = value?.pageSize || DEFAULT_DATASET_TABLE_SIZE;
  });

  function handleGoToFirstPage() {
    if (currentPage > 1) {
      isLoadingTableItems = true;
      datasetTableStore.update((value) => ({
        ...value,
        pageSize: value?.pageSize || pageSize,
        currentPage: 1,
      }));
    }
  }

  function handleGoToPreviousPage() {
    if (currentPage > 1) {
      isLoadingTableItems = true;
      datasetTableStore.update((value) => ({
        ...value,
        pageSize: value?.pageSize || pageSize,
        currentPage: currentPage - 1,
      }));
    }
  }

  function handleGoToNextPage() {
    if (selectedDataset.pagination.total_size > currentPage * pageSize) {
      isLoadingTableItems = true;
      datasetTableStore.update((value) => ({
        ...value,
        pageSize: value?.pageSize || pageSize,
        currentPage: currentPage + 1,
      }));
    }
  }

  function handleGoToLastPage() {
    if (selectedDataset.pagination.total_size > currentPage * pageSize) {
      isLoadingTableItems = true;
      datasetTableStore.update((value) => ({
        ...value,
        pageSize: value?.pageSize || pageSize,
        currentPage: Math.ceil((selectedDataset.pagination.total_size || 1) / pageSize),
      }));
    }
  }
</script>

{#if !selectedDataset.isErrored}
  <div class="w-full py-5 h-20 flex justify-center items-center text-slate-800">
    {#if selectedDataset.pagination.total_size > pageSize}
      <button on:click={handleGoToFirstPage}>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="48"
          viewBox="0 -960 960 960"
          width="48"
          class="h-8 w-8 p-1 rounded-full transition-colors hover:bg-slate-300"
        >
          <path d={svg_first_page} fill="currentcolor" />
        </svg>
      </button>

      <button on:click={handleGoToPreviousPage}>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="48"
          viewBox="0 -960 960 960"
          width="48"
          class="h-8 w-8 p-1 rounded-full transition-colors hover:bg-slate-300"
        >
          <path d={svg_prev_page} fill="currentcolor" />
        </svg>
      </button>
    {/if}

    <span class="mx-4">
      {1 + pageSize * (currentPage - 1)} - {Math.min(
        pageSize * currentPage,
        selectedDataset.pagination.total_size,
      )} of
      {selectedDataset.pagination.total_size}
    </span>

    {#if selectedDataset.pagination.total_size > pageSize}
      <button on:click={handleGoToNextPage}>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="48"
          viewBox="0 -960 960 960"
          width="48"
          class="h-8 w-8 p-1 rounded-full transition-colors hover:bg-slate-300"
        >
          <path d={svg_next_page} fill="currentcolor" />
        </svg>
      </button>

      <button on:click={handleGoToLastPage}>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="48"
          viewBox="0 -960 960 960"
          width="48"
          class="h-8 w-8 p-1 rounded-full transition-colors hover:bg-slate-300"
        >
          <path d={svg_last_page} fill="currentcolor" />
        </svg>
      </button>
    {/if}
  </div>
{/if}
