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

  import { datasetTableStore } from "../../lib/stores/datasetStores";
  import DatasetBrowserForm from "./DatasetBrowserForm.svelte";
  import DatasetPagination from "./DatasetPagination.svelte";

  // Exports
  export let selectedDataset: DatasetBrowser;
  let isLoadingTableItems = false;

  // Reactive statement to set isLoadingTableItems to false when table data is available
  $: {
    if (selectedDataset.table_data) {
      isLoadingTableItems = false;
    }
  }

  // Modals
  let loadingResultsModal = false;
  let datasetErrorModal = false;

  // Semantic search
  let searchInput: string = $datasetTableStore.query?.search ?? "";
  let selectedSearchModel: string | undefined;

  const dispatch = createEventDispatcher();

  // Function to handle item selection
  function handleSelectItem(itemId: string) {
    dispatch("selectItem", itemId);
  }

  // Function to clear the search input and trigger a new empty search
  function handleClearSearch() {
    searchInput = "";
    handleSearch();
  }

  // Function to handle search input changes
  function handleSearch() {
    let query = { model: selectedSearchModel as string, search: searchInput };
    isLoadingTableItems = true;
    datasetTableStore.update((value) => ({
      ...value,
      currentPage: 1,
      query,
    }));
  }

  // Function to handle filter changes
  function handleFilter(where: string) {
    datasetTableStore.update((value) => ({
      ...value,
      currentPage: 1,
      where,
    }));
  }

  function handleColSort(colsorts: { id: string; order: string }[]) {
    if (colsorts.length === 0) {
      //reset sort
      datasetTableStore.update((value) => {
        value = {
          ...value,
          currentPage: 1, //reset page
        };
        delete value.sort;
        return value;
      });
    } else if (colsorts.length === 1) {
      const { id, order } = colsorts[0];
      datasetTableStore.update((value) => ({
        ...value,
        currentPage: 1, //reset page
        sort: { col: id, order },
      }));
    } else {
      console.error("ERROR: MultiSort on columns is not managed nor allowed");
    }
  }
</script>

<div class="w-full px-20 bg-slate-50 flex flex-col text-slate-800 min-h-[calc(100vh-80px)]">
  {#if selectedDataset.pagination}
    <!-- Items list -->
    <DatasetBrowserForm
      {selectedDataset}
      bind:selectedSearchModel
      bind:searchInput
      on:search={handleSearch}
      on:clearSearch={handleClearSearch}
      on:filter={(event) => handleFilter(event.detail)}
    />

    <!-- Loading spinner while table items are being loaded -->
    {#if isLoadingTableItems}
      <div class="flex-grow flex justify-center items-center">
        <Loader2Icon class="animate-spin" />
      </div>
      <!-- Display table -->
    {:else if !selectedDataset.isErrored}
      <Table
        items={selectedDataset.table_data}
        disableSort={searchInput !== ""}
        on:selectItem={(event) => handleSelectItem(event.detail)}
        on:colsort={(event) => handleColSort(event.detail)}
      />
      <!-- Display error message if items could not be loaded -->
    {:else}
      <div
        class="flex flex-col gap-5 justify-center align-middle text-center max-w-xs m-auto mt-10"
      >
        <p>Error: dataset items could not be loaded</p>
        <PrimaryButton on:click={handleClearSearch}>Try again</PrimaryButton>
      </div>
    {/if}

    <!-- DatasetPagination component for page navigation -->
    <DatasetPagination {selectedDataset} bind:isLoadingTableItems />
  {/if}

  <!-- Warning modal for dataset errors -->
  {#if datasetErrorModal}
    <WarningModal
      message="Error while retrieving dataset items."
      details="Please look at the application logs for more information, and report this issue if the error persists."
      on:confirm={() => (datasetErrorModal = false)}
    />
  {/if}

  <!-- Loading modal while results are being loaded -->
  {#if loadingResultsModal}
    <LoadingModal />
  {/if}
</div>
