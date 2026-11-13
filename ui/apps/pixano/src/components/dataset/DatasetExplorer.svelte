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
  import { invalidate, invalidateAll } from "$app/navigation";
  import { navigating } from "$app/state";
  import {
    computeEmbeddings,
    getIoJob,
    listInferenceModels,
    setDefaultEmbeddingSpace,
  } from "$lib/api";
  import { ApiError, serverDetail } from "$lib/api/apiClient";
  import type { FilterSchemaResponse, IoJobResponse } from "$lib/api/restTypes";
  import { DEFAULT_DATASET_GRID_SIZE, DEFAULT_DATASET_TABLE_SIZE } from "$lib/constants";
  import type { SplitStatusCount } from "$lib/types/dataset";
  import { MultimodalImageNLPTask } from "$lib/types/inference";
  import type { DatasetBrowser } from "$lib/ui";
  import { describeTableColumns, undescribedStatisticColumns } from "$lib/utils/columns";
  import {
    embeddingsView,
    modelToCompute,
    orderedSpaces,
    selectedSpace,
  } from "$lib/utils/embeddingSpaces";
  import { EXPLORER_COLUMNS_DEPENDENCY } from "$lib/utils/explorerData";
  import { EXPLORER_ROUTE_ID } from "$lib/utils/routes";

  /** The status of an answer about a model the dataset holds no more. */
  const HTTP_NOT_FOUND = 404;

  interface Props {
    selectedDataset: DatasetBrowser;
    filterSchema: FilterSchemaResponse;
    splitCounts?: SplitStatusCount[];
    semanticActive?: boolean;
    /** Record id the current ranked view is "similar to" (find-similar mode). */
    similarTo?: string;
    /** The model a search reads, as the URL names it — its id —; empty for the default one. */
    model?: string;
    searchError?: string;
    /** What the explorer did of a URL it could not follow as it is: a model the dataset does not hold. */
    searchNotice?: string;
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
    model = "",
    searchError = "",
    searchNotice = "",
    view = "table",
    onSelectItem,
    onNavigate,
    pagination,
  }: Props = $props();
  const isLoadingTableItems = $derived(navigating.to?.route?.id === EXPLORER_ROUTE_ID);
  // The dataset's embeddings models, and the one a search reads — "more like this" too: the
  // URL's, else the default one.
  const spaces = $derived(orderedSpaces(filterSchema.search));
  const searchedSpace = $derived(selectedSpace(spaces, model));
  const embeddings = $derived(embeddingsView(filterSchema.search, spaces, searchedSpace));
  const semanticAvailable = $derived(embeddings.searchReady);
  const ranked = $derived(semanticActive || similarTo !== "");
  const isEmpty = $derived(selectedDataset.table_data.rows.length === 0);
  const hasActiveQuery = $derived(
    pagination.filters.length > 0 || pagination.q !== "" || similarTo !== "",
  );

  let computing = $state(false);
  let showConnectModal = $state(false);
  let computeJob = $state<IoJobResponse | null>(null);
  let settingDefault = $state(false);
  // The force a computation was asked with while no inference was connected: kept for after.
  let pendingForce = false;

  const datasetId = $derived(selectedDataset.id);

  // What went wrong computing the embeddings, and changing the default model, said for the dataset
  // it went wrong on: another dataset shown in place reuses this component.
  let computeFailure = $state<{ datasetId: string; message: string } | null>(null);
  let spaceFailure = $state<{ datasetId: string; message: string } | null>(null);
  const computeError = $derived(
    computeFailure?.datasetId === datasetId ? computeFailure.message : "",
  );
  const spaceError = $derived(spaceFailure?.datasetId === datasetId ? spaceFailure.message : "");

  async function runCompute(force = false): Promise<boolean> {
    // Returns false when no embedding model is reachable (caller prompts to connect).
    const models = await listInferenceModels();
    const embeddingModels = models.filter((m) => m.task === MultimodalImageNLPTask.EMBEDDING);
    if (embeddingModels.length === 0) return false;
    const computedFor = datasetId;
    computeFailure = null;
    // Forced on a description read in part, the computation deletes every model's embeddings and
    // starts again: whichever model is served then, the searched one first.
    const startAgain = force && !embeddings.descriptionReadable;
    const computed = modelToCompute(searchedSpace, spaces, embeddingModels, startAgain);
    if ("refusal" in computed) {
      computeFailure = { datasetId: computedFor, message: computed.refusal };
      return true;
    }
    let jobId: string;
    try {
      jobId = await computeEmbeddings(computedFor, computed.model, force, computed.provider);
    } catch (error) {
      computeFailure = {
        datasetId: computedFor,
        message: serverDetail(error) ?? "The embedding computation could not start.",
      };
      return true;
    }
    try {
      for (;;) {
        const job = await getIoJob(jobId);
        computeJob = job;
        if (["done", "error", "cancelled"].includes(job.status)) {
          if (job.status === "error") {
            computeFailure = {
              datasetId: computedFor,
              message: `Embedding computation failed: ${job.error?.message ?? "no reason given."}`,
            };
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

  // The page's columns named as the explorer names them: a statistic by its label and unit.
  const tableItems = $derived(
    describeTableColumns(selectedDataset.table_data, filterSchema.columns),
  );

  // A page can carry a statistic the explorer's columns, read before it was computed, do not
  // describe — a statistics job that ended after they were read: they are read again, once per such
  // column.
  let columnsAskedFor = "";
  $effect(() => {
    const undescribed = undescribedStatisticColumns(
      selectedDataset.table_data,
      filterSchema.columns,
    ).join(",");
    if (undescribed === "" || undescribed === columnsAskedFor) return;
    columnsAskedFor = undescribed;
    void invalidate(EXPLORER_COLUMNS_DEPENDENCY);
  });

  // Remount the table only when the dataset or its column set changes — the
  // table builds its column defs once at mount. Sorting is prop-driven and
  // re-renders in place (no remount, no scroll reset).
  // A column's label is part of it: the headers are built at mount, and a statistic gets its label
  // once the explorer's columns describe it.
  const tableKey = $derived(
    [
      selectedDataset.id,
      tableItems.columns.map((c) => `${c.name}\u0000${c.label ?? ""}`).join(","),
    ].join("|"),
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

  function handleSelectSpace(spaceId: string) {
    computeFailure = null;
    spaceFailure = null;
    // The default one is the URL naming none, so that the URL follows the dataset's default. Another
    // model ranks the records otherwise: a search running runs again, from its first page.
    const isDefault = spaces.some((space) => space.id === spaceId && space.default);
    onNavigate({ ...(ranked ? { page: "1" } : {}), model: isDefault ? undefined : spaceId });
  }

  async function handleSetDefaultSpace(spaceId: string) {
    if (settingDefault) return;
    const changedFor = datasetId;
    settingDefault = true;
    spaceFailure = null;
    try {
      await setDefaultEmbeddingSpace(changedFor, spaceId);
    } catch (error) {
      spaceFailure = {
        datasetId: changedFor,
        message: serverDetail(error) ?? "The default model could not be changed.",
      };
      // A model gone meanwhile: the list is read again.
      if (error instanceof ApiError && error.status === HTTP_NOT_FOUND) await invalidateAll();
      return;
    } finally {
      settingDefault = false;
    }
    // The search bar, and a search naming no model, read the default one.
    await invalidateAll();
  }

  async function handleCompute(force = false) {
    if (computing) return;
    computing = true;
    try {
      // If no embedding model is reachable, the server isn't connected — prompt for it, and
      // compute as asked once it is.
      const ok = await runCompute(force);
      if (!ok) {
        pendingForce = force;
        showConnectModal = true;
      }
    } finally {
      computing = false;
    }
  }

  async function handleConnected() {
    showConnectModal = false;
    computing = true;
    try {
      await runCompute(pendingForce);
    } finally {
      computing = false;
      pendingForce = false;
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
        {embeddings}
        {spaceError}
        {settingDefault}
        {searchNotice}
        {computing}
        computeProgress={computeJob?.progress ?? null}
        {computeError}
        {searchError}
        {view}
        onApply={handleApply}
        onSortChange={handleSortSelect}
        onCompute={handleCompute}
        onClearSimilar={handleClearSimilar}
        onSelectSpace={handleSelectSpace}
        onSetDefaultSpace={handleSetDefaultSpace}
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
              items={tableItems}
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
