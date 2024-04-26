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
  import { Loader2Icon } from "lucide-svelte";

  import { LoadingModal, WarningModal, PrimaryButton } from "@pixano/core/src";
  import { Table } from "@pixano/table";
  import type { ExplorerData, ItemFeature, ItemView } from "@pixano/core/src";

  import {
    svg_clear,
    svg_first_page,
    svg_last_page,
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
  export let selectedDataset: ExplorerData;
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
  console.log(selectedDataset)
  if (selectedDataset.sem_search.length > 0) {
    for (const model of selectedDataset.sem_search) {
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
    if (selectedDataset.pagination.total > currentPage * pageSize) {
      isLoadingTableItems = true;
      datasetTableStore.update((value) => ({
        ...value,
        pageSize: value?.pageSize || pageSize,
        currentPage: currentPage + 1,
      }));
    }
  }

  function handleGoToLastPage() {
    if (selectedDataset.pagination.total > currentPage * pageSize) {
      isLoadingTableItems = true;
      datasetTableStore.update((value) => ({
        ...value,
        pageSize: value?.pageSize || pageSize,
        currentPage: Math.ceil((selectedDataset.pagination.total || 1) / pageSize),
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

  // HACK TO CONVERT PREVIOUS TABLE INPUT TO NEW FORMAT
  // WILL NEED TO BE CHANGED/REMOVED ONCE THE NEW FORMAT IS SENT
  // let tableItems: Array<Array<ItemFeature>> = [];
  // selectedDataset.page?.items.forEach((item) => {
  //   let tableItem: Array<ItemFeature> = [];
  //   tableItem.push({ name: "id", dtype: "int", value: item.id });
  //   tableItem.push({ name: "split", dtype: "str", value: item.split });

  //   Object.values(item.views).forEach((view: ItemView) => {
  //     tableItem.push({
  //       name: view.id,
  //       dtype: "image",
  //       value: view.thumbnail ? view.thumbnail : "",
  //     });
  //   });

  //   Object.values(item.features).forEach((feature) => {
  //     tableItem.push({ name: feature.name, dtype: feature.dtype, value: feature.value });
  //   });

  //   tableItems.push(tableItem);
  // });
</script>

<div class="w-full px-20 bg-slate-50 flex flex-col text-slate-800 min-h-[calc(100vh-80px)]">
  {#if selectedDataset.pagination}
    <!-- Items list -->
    <div class="w-full h-full flex flex-col">
      <div class="py-5 h-20 flex space-x-2 items-center">
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
      </div>
      {#if isLoadingTableItems}
        <div class="flex-grow flex justify-center items-center">
          <Loader2Icon class="animate-spin" />
        </div>
      {:else if !selectedDataset.isErrored}
        <Table items={selectedDataset.table_data} on:selectItem={(event) => handleSelectItem(event.detail)} />
      {:else}
        <div
          class="flex flex-col gap-5 justify-center align-middle text-center max-w-xs m-auto mt-10"
        >
          <p>Error: dataset items could not be loaded</p>
          <PrimaryButton on:click={handleClearSearch}>Try again</PrimaryButton>
        </div>
      {/if}
    </div>

    {#if !selectedDataset.isErrored}
      <div class="w-full py-5 h-20 flex justify-center items-center text-slate-800">
        {#if selectedDataset.pagination.total > pageSize}
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
            selectedDataset.pagination.total,
          )} of
          {selectedDataset.pagination.total}
        </span>

        {#if selectedDataset.pagination.total > pageSize}
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
