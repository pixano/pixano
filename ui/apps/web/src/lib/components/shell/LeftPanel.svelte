<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { ArrowLeft, Box, FolderOpen, LayoutGrid, Loader2, Search } from "lucide-svelte";
  import { onMount } from "svelte";

  import { intersect } from "$lib/actions/intersect";
  import { listDatasets, listRecords } from "$lib/api/datasets";
  import type { RecordResponse } from "$lib/api/restTypes";
  import WidgetPalette from "$lib/components/sidebar/WidgetPalette.svelte";
  import type { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
  import type { DatasetInfo } from "$lib/types/dataset";
  import { measureGridViewport } from "$lib/workspace/layoutPlanner.js";
  import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

  interface Props {
    activeSection: string;
    registry: WidgetRegistry;
    manager: WorkspaceManager;
  }

  let { activeSection, registry, manager }: Props = $props();

  const sectionLabels: Record<string, { label: string; icon: typeof FolderOpen }> = {
    explorer: { label: "Explorer", icon: FolderOpen },
    widgets: { label: "Widgets", icon: LayoutGrid },
    search: { label: "Search", icon: Search },
  };

  let section = $derived(sectionLabels[activeSection] ?? sectionLabels.widgets);

  function handleWidgetAdd(extensionName: string) {
    manager.addWidget(extensionName);
  }

  const RECORDS_PAGE_SIZE = 50;

  // Records can expose several image views (e.g. nuScenes' 6 cameras); we compose
  // at most this many previews into the record's collage cell.
  const MAX_RECORD_PREVIEWS = 4;
  // Saturation/lightness for the fallback color tile shown when a record has no
  // image preview. Kept named so the tile reads clearly and stays consistent.
  const TILE_SATURATION = 55;
  const TILE_LIGHTNESS = 45;
  const HUE_RANGE = 360;
  // Odd prime multiplier for the record-id string hash (classic 31·h + c).
  const HASH_PRIME = 31;

  // Preview URLs whose <img> failed to load (missing/empty preview blob, 404…).
  // Excluded from the collage so a broken thumbnail falls back to the remaining
  // images, or to the color tile when none load — never the browser's broken
  // image glyph. Reassigned (not mutated) so the read below stays reactive.
  let failedPreviewUrls = $state<Set<string>>(new Set());

  function markPreviewFailed(url: string): void {
    if (failedPreviewUrls.has(url)) return;
    failedPreviewUrls = new Set(failedPreviewUrls).add(url);
  }

  /** The first few loadable image-view preview URLs, in declared view order. */
  function recordPreviewUrls(record: RecordResponse): string[] {
    return Object.values(record.view_previews ?? {})
      .filter((preview) => preview.kind === "image" && !failedPreviewUrls.has(preview.preview_url))
      .slice(0, MAX_RECORD_PREVIEWS)
      .map((preview) => preview.preview_url);
  }

  /**
   * A stable hue derived from a record id, so preview-less records still get a
   * distinct color tile (same id → same color, different ids → different colors).
   */
  function recordHue(id: string): number {
    let hash = 0;
    for (let i = 0; i < id.length; i++) {
      hash = (hash * HASH_PRIME + id.charCodeAt(i)) | 0;
    }
    return Math.abs(hash) % HUE_RANGE;
  }

  /** CSS background for a record's fallback tile. */
  function recordTileColor(id: string): string {
    return `hsl(${recordHue(id)} ${TILE_SATURATION}% ${TILE_LIGHTNESS}%)`;
  }

  /**
   * Grid span for one preview slot so the 2×2 collage cell is always fully
   * filled: 1 → whole cell, 2 → two full-height halves, 3 → two on top + one
   * spanning the bottom, 4 → an even 2×2.
   */
  function previewSlotClass(count: number, index: number): string {
    if (count === 1) return "col-span-2 row-span-2";
    if (count === 2) return "row-span-2";
    if (count === 3 && index === 2) return "col-span-2";
    return "";
  }

  type ExplorerView = "datasets" | "records";
  let explorerView = $state<ExplorerView>("datasets");
  let datasets = $state<DatasetInfo[]>([]);
  let records = $state<RecordResponse[]>([]);
  let selectedDataset = $state<DatasetInfo | null>(null);
  let loading = $state(false);
  let loadingMore = $state(false);
  let error = $state<string | null>(null);
  let recordsOffset = $state(0);
  let recordsTotal = $state(0);

  let hasMoreRecords = $derived(records.length < recordsTotal);

  onMount(async () => {
    loading = true;
    error = null;
    try {
      datasets = await listDatasets();
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load datasets";
    } finally {
      loading = false;
    }
  });

  async function openDataset(dataset: DatasetInfo) {
    selectedDataset = dataset;
    explorerView = "records";
    records = [];
    // New dataset → drop any preview failures recorded for the previous one so
    // the set can't grow across a session or exclude an unrelated URL.
    failedPreviewUrls = new Set();
    recordsOffset = 0;
    recordsTotal = 0;
    loading = true;
    error = null;
    try {
      const page = await listRecords(dataset.id, RECORDS_PAGE_SIZE, 0);
      records = page.items;
      recordsOffset = page.items.length;
      recordsTotal = page.total;
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load records";
    } finally {
      loading = false;
    }
  }

  async function loadMoreRecords() {
    if (!selectedDataset || loadingMore || !hasMoreRecords) return;
    loadingMore = true;
    error = null;
    try {
      const page = await listRecords(selectedDataset.id, RECORDS_PAGE_SIZE, recordsOffset);
      records = [...records, ...page.items];
      recordsOffset += page.items.length;
      recordsTotal = page.total;
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load more records";
    } finally {
      loadingMore = false;
    }
  }

  function goBack() {
    explorerView = "datasets";
    records = [];
    recordsOffset = 0;
    recordsTotal = 0;
    selectedDataset = null;
    error = null;
  }

  async function openRecord(recordId: string) {
    if (!selectedDataset) return;
    manager.clearWorkspace();
    // Measure the grid viewport from this component (which lives next to
    // GridWorkspace in the page) and pass it explicitly. Keeping the DOM
    // read here lets the manager stay environment-agnostic and unit-testable.
    const viewport = measureGridViewport();
    await manager.selectRecordInDataset(selectedDataset.id, recordId, viewport);
  }
</script>

<div class="flex h-full flex-col bg-background">
  <!-- Panel header -->
  <div class="flex h-10 items-center gap-2 border-b border-border px-3">
    {#if activeSection === "explorer" && explorerView === "records"}
      <button
        onclick={goBack}
        class="flex items-center gap-1.5 text-muted-foreground hover:text-foreground"
        aria-label="Back to datasets"
      >
        <ArrowLeft class="h-4 w-4" />
      </button>
      <span class="truncate text-xs font-semibold uppercase tracking-wider text-foreground">
        {selectedDataset?.name ?? "Records"}
      </span>
    {:else}
      <section.icon class="h-4 w-4 text-muted-foreground" />
      <span class="text-xs font-semibold uppercase tracking-wider text-foreground">
        {section.label}
      </span>
    {/if}
  </div>

  <!-- Panel content -->
  <div class="flex-1 overflow-y-auto">
    {#if activeSection === "widgets"}
      <WidgetPalette {registry} onWidgetAdd={handleWidgetAdd} />
    {:else if activeSection === "explorer"}
      {#if loading}
        <div class="flex items-center justify-center gap-2 p-6 text-xs text-muted-foreground">
          <Loader2 class="h-3.5 w-3.5 animate-spin" />
          <span>Loading…</span>
        </div>
      {:else if error}
        <p class="p-4 text-xs text-destructive">{error}</p>
      {:else if explorerView === "datasets"}
        <div class="p-3">
          {#if datasets.length === 0}
            <p class="text-xs text-muted-foreground">No datasets found.</p>
          {:else}
            <div class="space-y-1">
              {#each datasets as dataset (dataset.id)}
                <button
                  onclick={() => openDataset(dataset)}
                  class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs hover:bg-accent hover:text-accent-foreground"
                >
                  <FolderOpen class="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <span class="truncate">{dataset.name}</span>
                  <span class="ml-auto shrink-0 text-muted-foreground">{dataset.num_items}</span>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      {:else}
        <div class="p-3">
          {#if records.length === 0}
            <p class="text-xs text-muted-foreground">No records found.</p>
          {:else}
            <div class="space-y-1">
              {#each records as record (record.id)}
                {@const previews = recordPreviewUrls(record)}
                <button
                  onclick={() => openRecord(record.id)}
                  class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs hover:bg-accent hover:text-accent-foreground"
                >
                  <div
                    class="grid h-12 w-12 shrink-0 grid-cols-2 grid-rows-2 gap-px overflow-hidden rounded bg-border"
                  >
                    {#if previews.length === 0}
                      <div
                        class="col-span-2 row-span-2 flex items-center justify-center"
                        style="background: {recordTileColor(record.id)}"
                      >
                        <Box class="h-5 w-5 text-white/80" />
                      </div>
                    {:else}
                      {#each previews as url, i (url)}
                        <img
                          src={url}
                          alt=""
                          loading="lazy"
                          onerror={() => markPreviewFailed(url)}
                          class="h-full w-full object-cover {previewSlotClass(previews.length, i)}"
                        />
                      {/each}
                    {/if}
                  </div>
                  <span class="flex min-w-0 flex-col">
                    <span class="truncate font-mono text-muted-foreground">{record.id}</span>
                    {#if record.split}
                      <span class="truncate text-[10px] text-muted-foreground/70">
                        {record.split}
                      </span>
                    {/if}
                  </span>
                </button>
              {/each}
            </div>
            <div class="mt-3 flex flex-col items-center gap-2">
              <p class="text-xs text-muted-foreground" aria-live="polite">
                {records.length} / {recordsTotal}
              </p>
              {#if hasMoreRecords}
                <div
                  aria-hidden="true"
                  data-testid="records-sentinel"
                  use:intersect={{
                    onEnter: loadMoreRecords,
                    rootMargin: "200px",
                    enabled: !loadingMore,
                  }}
                ></div>
                <button
                  type="button"
                  onclick={loadMoreRecords}
                  disabled={loadingMore}
                  class="inline-flex items-center gap-1.5 rounded-md border border-input px-2 py-1 text-xs text-foreground hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {#if loadingMore}
                    <Loader2 class="h-3 w-3 animate-spin" />
                    <span>Loading…</span>
                  {:else}
                    <span>Load more</span>
                  {/if}
                </button>
              {/if}
            </div>
          {/if}
        </div>
      {/if}
    {:else if activeSection === "search"}
      <div class="p-3">
        <input
          type="text"
          placeholder="Search samples..."
          class="w-full rounded-md border border-input bg-muted/50 px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <p class="mt-3 text-xs text-muted-foreground">
          Type to search across datasets and annotations.
        </p>
      </div>
    {/if}
  </div>
</div>
