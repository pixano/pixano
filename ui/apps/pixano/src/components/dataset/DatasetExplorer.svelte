<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import ConnectToServerModal from "../inference/ConnectToServerModal.svelte";
  import DatasetPagination from "./DatasetPagination.svelte";
  import ExplorerEmptyState from "./ExplorerEmptyState.svelte";
  import GridSkeleton from "./GridSkeleton.svelte";
  import RecordFilterBar from "./RecordFilterBar.svelte";
  import RecordGrid from "./RecordGrid.svelte";
  import { Table } from "./table";
  import TableSkeleton from "./TableSkeleton.svelte";
  import { invalidateAll } from "$app/navigation";
  import { navigating } from "$app/state";
  import { computeEmbeddings, getIoJob, listInferenceModels } from "$lib/api";
  import type { FilterSchemaResponse, IoJobResponse } from "$lib/api/restTypes";
  import { DEFAULT_DATASET_GRID_SIZE, DEFAULT_DATASET_TABLE_SIZE } from "$lib/constants";
  import type { SplitStatusCount } from "$lib/types/dataset";
  import { MultimodalImageNLPTask } from "$lib/types/inference";
  import type { DatasetBrowser } from "$lib/ui";
  import { EXPLORER_ROUTE_ID } from "$lib/utils/routes";

  interface Props {
    selectedDataset: DatasetBrowser;
    filterSchema: FilterSchemaResponse;
    splitCounts?: SplitStatusCount[];
    semanticActive?: boolean;
    /** Record id the current ranked view is "similar to" (find-similar mode). */
    similarTo?: string;
    searchError?: string;
    view?: "grid" | "table";
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

  let {
    selectedDataset,
    filterSchema,
    splitCounts = [],
    semanticActive = false,
    similarTo = "",
    searchError = "",
    view = "table",
    onSelectItem,
    onNavigate,
    pagination,
  }: Props = $props();
  const isLoadingTableItems = $derived(navigating.to?.route?.id === EXPLORER_ROUTE_ID);
  const semanticAvailable = $derived((filterSchema.search?.modes ?? []).includes("semantic"));
  const ranked = $derived(semanticActive || similarTo !== "");
  const isEmpty = $derived(selectedDataset.table_data.rows.length === 0);
  const hasActiveQuery = $derived(
    pagination.filters.length > 0 || pagination.q !== "" || similarTo !== "",
  );

  let computing = $state(false);
  let showConnectModal = $state(false);
  let computeJob = $state<IoJobResponse | null>(null);
  let computeError = $state("");

  async function runCompute(): Promise<boolean> {
    // Returns false when no embedding model is reachable (caller prompts to connect).
    const models = await listInferenceModels();
    const embeddingModels = models.filter((m) => m.task === MultimodalImageNLPTask.EMBEDDING);
    if (embeddingModels.length === 0) return false;
    computeError = "";
    const jobId = await computeEmbeddings(selectedDataset.id, embeddingModels[0].name);
    try {
      for (;;) {
        const job = await getIoJob(jobId);
        computeJob = job;
        if (["done", "error", "cancelled"].includes(job.status)) {
          if (job.status === "error") {
            computeError = job.error?.message ?? "Embedding computation failed.";
          }
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
    } finally {
      computeJob = null;
    }
    await invalidateAll();
    return true;
  }

  // Remount the table only when the dataset or its column set changes — the
  // table builds its column defs once at mount. Sorting is prop-driven and
  // re-renders in place (no remount, no scroll reset).
  const tableKey = $derived(
    [selectedDataset.id, selectedDataset.table_data.columns.map((c) => c.name).join(",")].join("|"),
  );

  function handleSelectItem(itemId: string) {
    onSelectItem?.(itemId);
  }

  function handleApply(updates: { filter?: string[]; q?: string; semantic?: boolean }) {
    // Any filter/search change resets to the first page. Semantic search is ranked, so it
    // clears any column sort and the similar-to target.
    const semantic = updates.semantic;
    onNavigate({
      page: "1",
      filter: updates.filter,
      q: updates.q,
      semantic: semantic ? "1" : undefined,
      similar_to: undefined, // a text search or filter change exits find-similar mode
      ...(semantic ? { sort: undefined, order: undefined } : {}),
    });
  }

  function handleFindSimilar(recordId: string) {
    // Ranked by similarity to the record: keep filter chips (they prefilter), clear the
    // text query, semantic-text mode, and any column sort.
    onNavigate({
      page: "1",
      similar_to: recordId,
      q: undefined,
      semantic: undefined,
      sort: undefined,
      order: undefined,
    });
  }

  function handleClearSimilar() {
    onNavigate({ page: "1", similar_to: undefined });
  }

  async function handleCompute() {
    if (computing) return;
    computing = true;
    try {
      // If no embedding model is reachable, the server isn't connected — prompt for it.
      const ok = await runCompute();
      if (!ok) showConnectModal = true;
    } finally {
      computing = false;
    }
  }

  async function handleConnected() {
    showConnectModal = false;
    computing = true;
    try {
      await runCompute();
    } finally {
      computing = false;
    }
  }

  function handleColSort(colsorts: { id: string; order: string }[]) {
    if (colsorts.length === 0) {
      onNavigate({ page: "1", sort: undefined, order: undefined });
    } else {
      const { id, order } = colsorts[0];
      onNavigate({ page: "1", sort: id, order });
    }
  }

  function handleSortSelect(sort: string | undefined, order: string | undefined) {
    onNavigate({ page: "1", sort, order });
  }

  function handlePageChange(newPage: number) {
    onNavigate({ page: String(newPage) });
  }

  function handlePageSizeChange(size: number) {
    onNavigate({ page: "1", size: String(size) });
  }

  function handleViewChange(nextView: "grid" | "table") {
    if (nextView === view) return;
    // Remember the choice per dataset; switching views resets to page 1 with the
    // view's default page size.
    localStorage.setItem(`pixano.explorer.view.${selectedDataset.id}`, nextView);
    onNavigate({
      page: "1",
      view: nextView,
      size: String(nextView === "grid" ? DEFAULT_DATASET_GRID_SIZE : DEFAULT_DATASET_TABLE_SIZE),
    });
  }

  function handleClearAllForEmptyState() {
    onNavigate({
      page: "1",
      filter: undefined,
      q: undefined,
      semantic: undefined,
      similar_to: undefined,
    });
  }
</script>

<div class="flex-1 min-w-0 px-6 py-2 bg-background flex flex-col text-foreground overflow-hidden">
  {#if selectedDataset.pagination}
    <!-- Filter / search / sort toolbar -->
    <div class="shrink-0">
      <RecordFilterBar
        {filterSchema}
        filters={pagination.filters}
        q={pagination.q}
        total={selectedDataset.pagination.total_size}
        {splitCounts}
        sort={pagination.sort}
        order={pagination.order}
        {semanticActive}
        {similarTo}
        {computing}
        computeProgress={computeJob?.progress ?? null}
        {computeError}
        {searchError}
        {view}
        onApply={handleApply}
        onSortChange={handleSortSelect}
        onCompute={handleCompute}
        onClearSimilar={handleClearSimilar}
        onViewChange={handleViewChange}
      />
    </div>

    <!-- Main content area — the single card that owns border/rounding -->
    <div
      class="flex-1 min-h-0 overflow-hidden flex flex-col border border-border/50 rounded-xl bg-card shadow-elevation-1"
    >
      {#if isLoadingTableItems}
        {#if view === "grid"}
          <GridSkeleton count={pagination.size} />
        {:else}
          <TableSkeleton
            rows={pagination.size}
            columns={Math.min(selectedDataset.table_data.columns.length, 6)}
          />
        {/if}
      {:else if isEmpty}
        <ExplorerEmptyState
          {hasActiveQuery}
          onClear={hasActiveQuery ? handleClearAllForEmptyState : undefined}
        />
      {:else if view === "grid"}
        <RecordGrid
          cards={selectedDataset.card_data ?? []}
          {ranked}
          onOpen={handleSelectItem}
          onFindSimilar={semanticAvailable ? handleFindSimilar : undefined}
        />
      {:else}
        <div class="flex-1 min-h-0">
          {#key tableKey}
            <Table
              items={selectedDataset.table_data}
              activeSort={{ col: pagination.sort, order: pagination.order }}
              onSelectItem={handleSelectItem}
              onColsort={handleColSort}
              onFindSimilar={semanticAvailable ? handleFindSimilar : undefined}
            />
          {/key}
        </div>
      {/if}
    </div>

    <!-- Pagination — always visible at the bottom -->
    <div class="shrink-0">
      <DatasetPagination
        {selectedDataset}
        currentPage={pagination.currentPage}
        pageSize={pagination.size}
        pageSizeOptions={ranked ? [] : view === "grid" ? [24, 48, 96] : [20, 50, 100]}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
      />
    </div>
  {/if}
</div>

{#if showConnectModal}
  <ConnectToServerModal onClose={() => (showConnectModal = false)} onConnected={handleConnected} />
{/if}
