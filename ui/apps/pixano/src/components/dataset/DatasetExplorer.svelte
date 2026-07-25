<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { CircleNotch } from "phosphor-svelte";

  import ConnectToServerModal from "../inference/ConnectToServerModal.svelte";
  import DatasetPagination from "./DatasetPagination.svelte";
  import RecordFilterBar from "./RecordFilterBar.svelte";
  import { Table } from "./table";
  import { invalidateAll } from "$app/navigation";
  import { navigating } from "$app/state";
  import { computeEmbeddings, getIoJob, listInferenceModels } from "$lib/api";
  import type { FilterSchemaResponse, IoJobResponse } from "$lib/api/restTypes";
  import { MultimodalImageNLPTask } from "$lib/types/inference";
  import type { DatasetBrowser } from "$lib/ui";
  import { EXPLORER_ROUTE_ID } from "$lib/utils/routes";

  interface Props {
    selectedDataset: DatasetBrowser;
    filterSchema: FilterSchemaResponse;
    semanticActive?: boolean;
    /** Record id the current ranked view is "similar to" (find-similar mode). */
    similarTo?: string;
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
    semanticActive = false,
    similarTo = "",
    onSelectItem,
    onNavigate,
    pagination,
  }: Props = $props();
  const isLoadingTableItems = $derived(navigating.to?.route?.id === EXPLORER_ROUTE_ID);
  const semanticAvailable = $derived((filterSchema.search?.modes ?? []).includes("semantic"));

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
          {semanticActive}
          {similarTo}
          {computing}
          computeProgress={computeJob?.progress ?? null}
          {computeError}
          onApply={handleApply}
          onCompute={handleCompute}
          onClearSimilar={handleClearSimilar}
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
                onFindSimilar={semanticAvailable ? handleFindSimilar : undefined}
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

{#if showConnectModal}
  <ConnectToServerModal onClose={() => (showConnectModal = false)} onConnected={handleConnected} />
{/if}
