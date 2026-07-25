<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { CircleNotch } from "phosphor-svelte";

  import DatasetPagination from "./DatasetPagination.svelte";
  import RecordFilterBar from "./RecordFilterBar.svelte";
  import { Table } from "./table";
  import { navigating } from "$app/state";
  import type { FilterSchemaResponse } from "$lib/api/restTypes";
  import type { DatasetBrowser } from "$lib/ui";
  import { EXPLORER_ROUTE_ID } from "$lib/utils/routes";

  interface Props {
    selectedDataset: DatasetBrowser;
    filterSchema: FilterSchemaResponse;
    onSelectItem?: (itemId: string) => void;
    onNavigate: (updates: Record<string, string | string[] | undefined>) => void;
    pagination: {
      currentPage: number;
      size: number;
      sort: string;
      order: string;
      filters: string[];
      q: string;
      where: string;
    };
  }

  let { selectedDataset, filterSchema, onSelectItem, onNavigate, pagination }: Props = $props();
  const isLoadingTableItems = $derived(navigating.to?.route?.id === EXPLORER_ROUTE_ID);

  // Remount the table when the dataset, its column set, or the active sort
  // changes: the table builds its column defs and initial sort state once at
  // mount, so a key keeps them in sync with the server-driven query.
  const tableKey = $derived(
    [
      selectedDataset.id,
      selectedDataset.table_data.columns.map((c) => c.name).join(","),
      pagination.sort,
      pagination.order,
    ].join("|"),
  );

  function handleSelectItem(itemId: string) {
    onSelectItem?.(itemId);
  }

  function handleApply(updates: { filter?: string[]; q?: string }) {
    // Any filter/search change resets to the first page.
    onNavigate({ page: "1", ...updates });
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
    onNavigate({ page: String(newPage) });
  }
</script>

<div class="flex-1 min-w-0 px-6 py-4 bg-background flex flex-col text-foreground overflow-hidden">
  <div class="max-w-[1400px] w-full mx-auto flex flex-col h-full">
    {#if selectedDataset.pagination}
      <!-- Filter / search / sort toolbar -->
      <div class="shrink-0">
        <RecordFilterBar
          {filterSchema}
          filters={pagination.filters}
          q={pagination.q}
          total={selectedDataset.pagination.total_size}
          onApply={handleApply}
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
        {:else}
          <div class="flex-1 min-h-0">
            {#key tableKey}
              <Table
                items={selectedDataset.table_data}
                activeSort={{ col: pagination.sort, order: pagination.order }}
                onSelectItem={handleSelectItem}
                onColsort={handleColSort}
              />
            {/key}
          </div>
        {/if}
      </div>

      <!-- Pagination — always visible at the bottom -->
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
</div>
