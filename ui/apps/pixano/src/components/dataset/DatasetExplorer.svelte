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

  function handleSelectItem(itemId: string) {
    dispatch("selectItem", itemId);
  }

  function handleClearSearch() {
    searchInput = "";
    handleSearch();
  }

  function handleSearch() {
    let query = { model: selectedSearchModel as string, search: searchInput };
    isLoadingTableItems = true;
    datasetTableStore.update((value) => ({
      ...value,
      currentPage: 1,
      query,
    }));
  }

  function handleFilter(where: string) {
    datasetTableStore.update((value) => ({
      ...value,
      currentPage: 1,
      where,
    }));
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

    <DatasetPagination {selectedDataset} bind:isLoadingTableItems />
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
