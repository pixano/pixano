<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { CircleNotch } from "phosphor-svelte";

  import type { DatasetBrowser } from "$lib/ui";
  import { LoadingModal, PrimaryButton, WarningModal } from "$lib/ui";
  import { Table } from "./table";

  import DatasetBrowserForm from "./DatasetBrowserForm.svelte";
  import DatasetPagination from "./DatasetPagination.svelte";

  interface Props {
    selectedDataset: DatasetBrowser;
    onSelectItem?: (itemId: string) => void;
    onNavigate: (updates: Record<string, string | undefined>) => void;
    pagination: {
      currentPage: number;
      size: number;
      sort?: { col: string; order: string };
      query?: { model: string; search: string };
      where: string;
    };
  }

  let { selectedDataset, onSelectItem, onNavigate, pagination }: Props = $props();
  let isLoadingTableItems = $state(false);

  // Reactive statement to set isLoadingTableItems to false when table data is available or on error
  $effect(() => {
    if (selectedDataset.table_data || selectedDataset.isErrored) {
      isLoadingTableItems = false;
    }
  });

  // Modals
  let loadingResultsModal = false;
  let datasetErrorModal = $state(false);

  // Semantic search — local editable copies, re-synced when URL params change
  let searchInput: string = $state("");
  let selectedSearchModel: string | undefined = $state();

  $effect(() => {
    searchInput = pagination.query?.search ?? "";
    selectedSearchModel = pagination.query?.model;
  });

  // Function to handle item selection
  function handleSelectItem(itemId: string) {
    onSelectItem?.(itemId);
  }

  // Function to clear the search input and trigger a new empty search
  function handleClearSearch() {
    searchInput = "";
    isLoadingTableItems = true;
    onNavigate({ page: "1", q: undefined, model: undefined });
  }

  // Function to handle search input changes
  function handleSearch() {
    isLoadingTableItems = true;
    onNavigate({ page: "1", q: searchInput, model: selectedSearchModel });
  }

  // Function to handle filter changes
  function handleFilter(where: string) {
    onNavigate({ page: "1", filter: where || undefined });
  }

  function handleColSort(colsorts: { id: string; order: string }[]) {
    if (colsorts.length === 0) {
      onNavigate({ page: "1", sort: undefined, order: undefined });
    } else if (colsorts.length === 1) {
      const { id, order } = colsorts[0];
      onNavigate({ page: "1", sort: id, order });
    } else {
      console.error("ERROR: MultiSort on columns is not managed nor allowed");
    }
  }

  function handlePageChange(newPage: number) {
    isLoadingTableItems = true;
    onNavigate({ page: String(newPage) });
  }
</script>

<div class="flex-1 min-w-0 px-6 py-4 bg-background flex flex-col text-foreground overflow-hidden">
  <div class="max-w-[1400px] w-full mx-auto flex flex-col h-full">
    {#if selectedDataset.pagination}
      <!-- Header Area (Search/Filter) -->
      <div class="shrink-0 mb-2">
        <DatasetBrowserForm
          {selectedDataset}
          bind:selectedSearchModel
          bind:searchInput
          onSearch={handleSearch}
          onClearSearch={handleClearSearch}
          onFilter={handleFilter}
        />
      </div>

      <!-- Main Table Area - This should scroll -->
      <div
        class="flex-1 min-h-0 overflow-hidden flex flex-col border border-border/50 rounded-xl bg-card shadow-sm"
      >
        {#if isLoadingTableItems}
          <div class="flex-grow flex justify-center items-center">
            <CircleNotch weight="regular" class="animate-spin text-primary opacity-50" />
          </div>
          <!-- Display table -->
        {:else if !selectedDataset.isErrored}
          <div class="flex-1 min-h-0">
            <Table
              items={selectedDataset.table_data}
              disableSort={searchInput !== ""}
              onSelectItem={handleSelectItem}
              onColsort={handleColSort}
            />
          </div>
          <!-- Display error message if items could not be loaded -->
        {:else}
          <div
            class="flex flex-col gap-5 justify-center align-middle text-center max-w-xs m-auto mt-10"
          >
            <p class="text-muted-foreground italic">Error: dataset items could not be loaded</p>
            <PrimaryButton onclick={handleClearSearch}>Try again</PrimaryButton>
          </div>
        {/if}
      </div>

      <!-- DatasetPagination component for page navigation - Always visible at bottom -->
      <div class="shrink-0 pt-2">
        <DatasetPagination
          {selectedDataset}
          currentPage={pagination.currentPage}
          pageSize={pagination.size}
          onPageChange={handlePageChange}
        />
      </div>
    {/if}
  </div>

  <!-- Warning modal for dataset errors -->
  {#if datasetErrorModal}
    <WarningModal
      message="Error while retrieving dataset items."
      details="Please look at the application logs for more information, and report this issue if the error persists."
      onConfirm={() => (datasetErrorModal = false)}
    />
  {/if}

  <!-- Loading modal while results are being loaded -->
  {#if loadingResultsModal}
    <LoadingModal />
  {/if}
</div>
