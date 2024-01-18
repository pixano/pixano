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
  import { Loader2Icon } from "lucide-svelte";

  import { LoadingModal, WarningModal } from "@pixano/core/src";
  import { Table } from "@pixano/table";
  import type { DatasetInfo } from "@pixano/core/src";

  import {
    svg_clear,
    svg_filter,
    svg_first_page,
    svg_grid,
    svg_last_page,
    svg_list,
    svg_next_page,
    svg_prev_page,
    svg_search,
  } from "@pixano/core/src/icons";

  import { datasetTableStore } from "../../lib/stores/datasetStores";
  import {
    DEFAULT_DATASET_TABLE_PAGE,
    DEFAULT_DATASET_TABLE_SIZE,
  } from "$lib/constants/pixanoConstants";

  // Exports
  export let selectedDataset: DatasetInfo;
  let isLoadingTableItems = false;

  // Page navigation
  let currentPage: number;
  let pageSize: number;
  $: {
    if (selectedDataset.page?.items) {
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
  let search: string = "";
  let selectedSearchModel: string | undefined;
  const searchModels: string[] = [];
  if ("embeddings" in selectedDataset.tables) {
    for (const table of selectedDataset.tables.embeddings) {
      if (table.type == "search") {
        // Initialize selected search model
        if (!selectedSearchModel) {
          selectedSearchModel = table.source;
        }
        searchModels.push(table.source as string);
      }
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
    isLoadingTableItems = true;
    if (currentPage > 1) {
      datasetTableStore.update((value) => ({
        ...value,
        pageSize: value?.pageSize || pageSize,
        currentPage: 1,
      }));
    }
  }

  function handleGoToPreviousPage() {
    isLoadingTableItems = true;
    if (currentPage > 1) {
      datasetTableStore.update((value) => ({
        ...value,
        pageSize: value?.pageSize || pageSize,
        currentPage: currentPage - 1,
      }));
    }
  }

  function handleGoToNextPage() {
    isLoadingTableItems = true;
    if ((selectedDataset.page?.total || 1) > currentPage * pageSize) {
      datasetTableStore.update((value) => ({
        ...value,
        pageSize: value?.pageSize || pageSize,
        currentPage: currentPage + 1,
      }));
    }
  }

  function handleGoToLastPage() {
    isLoadingTableItems = true;
    if ((selectedDataset.page?.total || 1) > currentPage * pageSize) {
      datasetTableStore.update((value) => ({
        ...value,
        pageSize: value?.pageSize || pageSize,
        currentPage: Math.ceil((selectedDataset.page?.total || 1) / pageSize),
      }));
    }
  }

  function handleSearch() {
    search = (document.getElementById("sem-search-input") as HTMLInputElement).value;
    let query = { model: selectedSearchModel as string, search };
    isLoadingTableItems = true;
    datasetTableStore.update((value) => ({
      ...value,
      currentPage: 1,
      query,
    }));
  }

  onMount(() => {
    search = "";
  });
</script>

<div class="w-full px-20 flex flex-col bg-slate-100 text-slate-800 min-h-[calc(100vh-80px)]">
  {#if selectedDataset.page}
    <!-- Items list -->
    <div class="w-full h-full flex flex-col">
      <div class="py-5 h-20 flex space-x-2 items-center">
        <button>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="h-8 w-8 p-1 rounded-full transition-colors hover:bg-slate-300"
          >
            <path d={svg_list} fill="currentcolor" />
          </svg>
        </button>
        <button>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="h-8 w-8 p-1 rounded-full transition-colors hover:bg-slate-300"
          >
            <path d={svg_grid} fill="currentcolor" />
          </svg>
        </button>
        <button>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="h-8 w-8 p-1 rounded-full transition-colors hover:bg-slate-300"
          >
            <path d={svg_filter} fill="currentcolor" />
          </svg>
        </button>
        <div class="flex-grow" />
        <div class="relative flex items-center">
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
                value={search}
                placeholder="Semantic search using {selectedSearchModel}"
                class="h-10 pl-10 pr-4 rounded-full border text-slate-800 placeholder-slate-500 bg-slate-50 border-slate-300 shadow-slate-300 accent-main"
                on:change={handleSearch}
              />
              <svg
                xmlns="http://www.w3.org/2000/svg"
                height="48"
                viewBox="0 -960 960 960"
                width="48"
                class="absolute left-2 h-5 w-5 text-slate-500 pointer-events-none"
              >
                <path d={svg_search} fill="currentcolor" />
              </svg>
              {#if search !== ""}
                <button
                  class="absolute right-2 p-1 rounded-full transition-colors hover:bg-slate-300"
                  on:click={handleClearSearch}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    height="48"
                    viewBox="0 -960 960 960"
                    width="48"
                    class="h-5 w-5 text-slate-500"
                  >
                    <path d={svg_clear} fill="currentcolor" />
                  </svg>
                </button>
              {/if}
            </div>
          {/if}
        </div>
      </div>
      {#if isLoadingTableItems}
        <div class="flex-grow flex justify-center items-center">
          <Loader2Icon class="animate-spin" />
        </div>
      {:else}
        <Table
          items={selectedDataset.page.items}
          on:selectItem={(event) => handleSelectItem(event.detail)}
        />
      {/if}
    </div>

    <div class="w-full py-5 h-20 flex justify-center items-center text-slate-800">
      {#if selectedDataset.page.total > pageSize}
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
          selectedDataset.page.total,
        )} of
        {selectedDataset.page.total}
      </span>

      {#if selectedDataset.page.total > pageSize}
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
