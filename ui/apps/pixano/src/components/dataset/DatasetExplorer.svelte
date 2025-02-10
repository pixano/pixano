<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Loader2Icon } from "lucide-svelte";
  import { createEventDispatcher } from "svelte";

  import type { DatasetBrowser } from "@pixano/core/src";
  import { LoadingModal, PrimaryButton, WarningModal } from "@pixano/core/src";
  import { Table } from "@pixano/table";

  import {
    svg_clear,
    svg_first_page,
    svg_last_page,
    svg_next_page,
    svg_prev_page,
    svg_search,
  } from "@pixano/core/src/icons";

  import {
    DEFAULT_DATASET_TABLE_PAGE,
    DEFAULT_DATASET_TABLE_SIZE,
  } from "$lib/constants/pixanoConstants";
  import { datasetTableStore } from "../../lib/stores/datasetStores";

  // Exports
  export let selectedDataset: DatasetBrowser;
  let isLoadingTableItems = false;

  // Page navigation
  let currentPage: number;
  let pageSize: number;
  $: {
    if (selectedDataset.table_data) {
      isLoadingTableItems = false;
    }
  }

  datasetTableStore.subscribe((value) => {
    currentPage = value?.currentPage || DEFAULT_DATASET_TABLE_PAGE;
    pageSize = value?.pageSize || DEFAULT_DATASET_TABLE_SIZE;
  });

  // Modals
  let loadingResultsModal = false;
  let datasetErrorModal = false;

  // Semantic search
  let searchInput: string = "";
  let selectedSearchModel: string | undefined;
  const searchModels: string[] = [];
  if (selectedDataset.semantic_search.length > 0) {
    for (const model of selectedDataset.semantic_search) {
      // Initialize selected search model
      if (!selectedSearchModel) {
        selectedSearchModel = model;
      }
      searchModels.push(model);
    }
  }

  const dispatch = createEventDispatcher();

  function handleSelectItem(itemId: string) {
    dispatch("selectItem", itemId);
  }

  function handleClearSearch() {
    (document.getElementById("sem-search-input") as HTMLInputElement).value = "";
    handleSearch();
  }

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

  function handleSearch() {
    searchInput = (document.getElementById("sem-search-input") as HTMLInputElement).value;
    let query = { model: selectedSearchModel as string, search: searchInput };
    isLoadingTableItems = true;
    datasetTableStore.update((value) => ({
      ...value,
      currentPage: 1,
      query,
    }));
  }
</script>

<div class="w-full px-20 bg-slate-50 flex flex-1 flex-col text-slate-800 max-h-screen">
  {#if selectedDataset.pagination}
    <!-- Items list -->
    <div class="ml-auto flex items-center py-5 h-20 space-x-2">
      {#if searchModels.length > 0}
        <select class="h-10 px-4 mx-4 border rounded bg-slate-50 border-slate-300">
          {#each searchModels as model}
            <option value={selectedSearchModel}>
              {model}
            </option>
          {/each}
        </select>
        <div class="relative flex items-center">
          <input
            id="sem-search-input"
            type="text"
            value={searchInput}
            placeholder="Semantic search using {selectedSearchModel}"
            class="h-10 pl-10 pr-4 rounded-full border text-slate-800 placeholder-slate-500 bg-slate-50 border-slate-300 shadow-slate-300 accent-main"
            on:change={handleSearch}
          />
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="absolute left-2 h-5 w-5 text-slate-800 pointer-events-none"
          >
            <path d={svg_search} fill="currentcolor" />
          </svg>
          {#if searchInput !== ""}
            <button
              class="absolute right-2 p-1 rounded-full transition-colors hover:bg-slate-300"
              on:click={handleClearSearch}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                height="48"
                viewBox="0 -960 960 960"
                width="48"
                class="h-5 w-5 text-slate-800"
              >
                <path d={svg_clear} fill="currentcolor" />
              </svg>
            </button>
          {/if}
        </div>
      {/if}
    </div>
    {#if isLoadingTableItems}
      <div class="flex-grow flex justify-center items-center">
        <Loader2Icon class="animate-spin" />
      </div>
    {:else if !selectedDataset.isErrored}
      <Table
        items={selectedDataset.table_data}
        on:selectItem={(event) => handleSelectItem(event.detail)}
      />
    {:else}
      <div
        class="flex flex-col gap-5 justify-center align-middle text-center max-w-xs m-auto mt-10"
      >
        <p>Error: dataset items could not be loaded</p>
        <PrimaryButton on:click={handleClearSearch}>Try again</PrimaryButton>
      </div>
    {/if}

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
  {/if}
  {#if datasetErrorModal}
    <WarningModal
      message="Error while retrieving dataset items."
      details="Please look at the application logs for more information, and report this issue if the error persists."
      on:confirm={() => (datasetErrorModal = false)}
    />
  {/if}
  {#if loadingResultsModal}
    <LoadingModal />
  {/if}
</div>
