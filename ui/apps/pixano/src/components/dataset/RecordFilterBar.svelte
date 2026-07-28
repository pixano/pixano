<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Popover } from "bits-ui";
  import {
    ArrowsClockwise,
    ArrowsDownUp,
    CaretDown,
    CircleNotch,
    FunnelSimple,
    Images,
    MagnifyingGlass,
    Plus,
    Rows,
    SortAscending,
    SortDescending,
    SquaresFour,
    Warning,
    X,
  } from "phosphor-svelte";

  import FacetSelect from "./FacetSelect.svelte";
  import FilterChipEditor from "./FilterChipEditor.svelte";
  import type {
    ColumnDescriptorResponse,
    FilterSchemaResponse,
    IoJobResponse,
  } from "$lib/api/restTypes";
  import type { SplitStatusCount } from "$lib/types/dataset";
  import { Select } from "$lib/ui";
  import { formatColumnLabel } from "$lib/utils/columns";
  import {
    isListOperator,
    OPERATOR_LABELS,
    parseFilters,
    serializeFilters,
    type RecordFilter,
  } from "$lib/utils/recordFilters";

  interface Props {
    filterSchema: FilterSchemaResponse;
    filters: string[];
    q: string;
    total: number;
    splitCounts?: SplitStatusCount[];
    sort?: string;
    order?: string;
    semanticActive?: boolean;
    /** Record id the current ranked view is "similar to" (find-similar mode). */
    similarTo?: string;
    computing?: boolean;
    /** Live progress of the embedding-compute job (while `computing`). */
    computeProgress?: IoJobResponse["progress"] | null;
    computeError?: string;
    searchError?: string;
    view?: "grid" | "table";
    onApply: (updates: { filter?: string[]; q?: string; semantic?: boolean }) => void;
    onSortChange?: (sort: string | undefined, order: string | undefined) => void;
    onCompute?: (force?: boolean) => void;
    onClearSimilar?: () => void;
    onViewChange?: (view: "grid" | "table") => void;
  }

  let {
    filterSchema,
    filters,
    q,
    total,
    splitCounts = [],
    sort = "",
    order = "asc",
    semanticActive = false,
    similarTo = "",
    computing = false,
    computeProgress = null,
    computeError = "",
    searchError = "",
    view = "table",
    onApply,
    onSortChange,
    onCompute,
    onClearSimilar,
    onViewChange,
  }: Props = $props();

  const columns = $derived(filterSchema.columns);
  const embeddingsStatus = $derived(filterSchema.search?.status ?? "absent");
  const embeddingsDetail = $derived(filterSchema.search?.detail ?? "");
  const embeddingsDegraded = $derived(
    ["missing_table", "empty", "dim_mismatch", "corrupt"].includes(embeddingsStatus),
  );
  const embeddedRows = $derived(filterSchema.search?.embedded_rows ?? 0);
  const totalRecords = $derived(filterSchema.search?.total_records ?? 0);
  const embeddingModelId = $derived(filterSchema.search?.models?.[0] ?? "");
  // The search bar is semantic-only; exact matching is the filters' job.
  const searchReady = $derived(embeddingsStatus === "ready" || embeddingsStatus === "partial");
  const sortableColumns = $derived(columns.filter((c) => c.sortable));
  const ranked = $derived(semanticActive || similarTo !== "");
  const sortItems = $derived([
    { value: "", label: "Default order" },
    ...sortableColumns.map((c) => ({ value: c.name, label: formatColumnLabel(c.name) })),
  ]);

  // Embedding-tools popover (grouped inside the search bar).
  let toolsOpen = $state(false);

  // Active filters, parsed from the URL-sourced tokens.
  const activeFilters = $derived(parseFilters(filters));

  // Local, editable copy of the search box; re-synced when the URL changes.
  let searchInput = $state("");
  $effect(() => {
    searchInput = q;
  });

  // Editor state: null = closed, -1 = adding, >=0 = editing that filter.
  let editorIndex = $state<number | null>(null);

  let searchErrorDismissed = $state(false);
  $effect(() => {
    // A fresh load result resets the dismissal.
    void searchError;
    searchErrorDismissed = false;
  });

  // ---- Facets (split / status quick filters over the generic chip machinery) ----

  function facetColumn(name: string): ColumnDescriptorResponse | undefined {
    return columns.find((c) => c.name === name && c.filterable && c.values);
  }

  function facetValues(name: "split" | "status"): { value: string; count?: number }[] {
    const column = facetColumn(name);
    if (!column?.values) return [];
    const counts = new Map<string, number>();
    for (const entry of splitCounts) {
      const key = name === "split" ? entry.split : entry.status;
      counts.set(key, (counts.get(key) ?? 0) + entry.count);
    }
    return column.values.map((value) => ({ value, count: counts.get(value) }));
  }

  function facetSelected(name: string): string[] {
    // The facet owns single eq/in filters on its column.
    const filter = activeFilters.find((f) => f.col === name && (f.op === "in" || f.op === "eq"));
    return filter ? filter.values : [];
  }

  function handleFacetChange(name: string, values: string[]) {
    const rest = activeFilters.filter((f) => !(f.col === name && (f.op === "in" || f.op === "eq")));
    const next =
      values.length > 0 ? [...rest, { col: name, op: "in", values } satisfies RecordFilter] : rest;
    applyFilters(next);
  }

  const splitFacet = $derived(facetValues("split"));
  const statusFacet = $derived(facetValues("status"));

  // ---- Filters / search ----

  function applyFilters(next: RecordFilter[]) {
    onApply({ filter: serializeFilters(next) });
  }

  function handleSaveFilter(filter: RecordFilter) {
    const next = [...activeFilters];
    if (editorIndex === null || editorIndex < 0) next.push(filter);
    else next[editorIndex] = filter;
    editorIndex = null;
    applyFilters(next);
  }

  function removeFilter(index: number) {
    applyFilters(activeFilters.filter((_, i) => i !== index));
  }

  function clearAll() {
    onApply({ filter: [], q: undefined, semantic: false });
  }

  function submitSearch() {
    if (!searchReady || computing) return;
    const text = searchInput.trim();
    onApply({ q: text || undefined, semantic: text !== "" });
  }

  function clearSearch() {
    searchInput = "";
    onApply({ q: undefined, semantic: false });
  }

  function runCompute(force: boolean) {
    toolsOpen = false;
    onCompute?.(force);
  }

  function chipLabel(filter: RecordFilter): string {
    const op = OPERATOR_LABELS[filter.op] ?? filter.op;
    const value = isListOperator(filter.op) ? filter.values.join(", ") : (filter.values[0] ?? "");
    return `${formatColumnLabel(filter.col)} ${op} ${value}`;
  }

  // ---- Compute progress ----

  const computeDone = $derived(computeProgress?.done ?? 0);
  const computeTotal = $derived(computeProgress?.total ?? null);
  const computePercent = $derived(
    computeTotal ? Math.min(100, Math.round((computeDone / computeTotal) * 100)) : null,
  );
</script>

<div class="flex flex-col gap-2.5 py-3">
  <!-- Row 1 — search, mode, facets, filters · sort, count -->
  <div class="flex items-center justify-between gap-4 flex-wrap">
    <div class="flex items-center gap-3 flex-1 min-w-0 flex-wrap">
      <!-- Semantic search bar — every embedding tool lives inside it. -->
      <div class="relative group flex-1 min-w-[240px] max-w-md">
        <MagnifyingGlass
          size={16}
          class="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none transition-colors {ranked
            ? 'text-primary'
            : 'text-muted-foreground/60 group-focus-within:text-primary'}"
        />
        <input
          type="text"
          bind:value={searchInput}
          onkeydown={(e) => e.key === "Enter" && submitSearch()}
          disabled={!searchReady || computing}
          placeholder={computing
            ? "Computing embeddings…"
            : searchReady
              ? "Search by meaning…"
              : embeddingsDegraded
                ? "Semantic search needs repair"
                : "Semantic search — not enabled yet"}
          class="h-10 w-full pl-10 pr-24 rounded-xl bg-muted/50 border text-sm text-foreground placeholder-muted-foreground/60 shadow-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:bg-background disabled:cursor-not-allowed disabled:opacity-70 {ranked
            ? 'border-primary/40'
            : 'border-border'}"
        />
        <div class="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {#if searchInput !== "" && searchReady && !computing}
            <button
              type="button"
              onclick={clearSearch}
              aria-label="Clear search"
              class="p-0.5 rounded-full hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <X size={14} />
            </button>
          {/if}

          {#if computing}
            <span
              class="inline-flex items-center gap-1.5 text-xs text-muted-foreground tabular-nums"
            >
              <CircleNotch size={13} class="animate-spin" />
              {computePercent !== null ? `${computePercent}%` : ""}
            </span>
          {:else if embeddingsDegraded && onCompute}
            <button
              type="button"
              onclick={() => runCompute(true)}
              title={embeddingsDetail ||
                "The embedding store is broken; recompute it from scratch."}
              class="inline-flex items-center gap-1 h-7 px-2.5 rounded-lg border border-warning/50 bg-warning/10 text-[11px] font-bold uppercase tracking-wider text-warning hover:bg-warning/20 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <ArrowsClockwise size={12} />
              Repair
            </button>
          {:else if embeddingsStatus === "absent" && onCompute}
            <button
              type="button"
              onclick={() => runCompute(false)}
              title="Compute embeddings to enable semantic search"
              class="inline-flex items-center h-7 px-2.5 rounded-lg bg-primary text-primary-foreground text-[11px] font-bold uppercase tracking-wider hover:bg-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Enable
            </button>
          {:else if searchReady && onCompute}
            <Popover.Root bind:open={toolsOpen}>
              <Popover.Trigger
                aria-label="Embedding options"
                title="Embedding options"
                class={embeddingsStatus === "partial"
                  ? "inline-flex items-center gap-1 h-7 px-2 rounded-lg border border-warning/50 bg-warning/10 text-[11px] font-bold text-warning tabular-nums hover:bg-warning/20 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  : "inline-flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground/60 hover:text-foreground hover:bg-accent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"}
              >
                {#if embeddingsStatus === "partial"}
                  {embeddedRows.toLocaleString()}/{totalRecords.toLocaleString()}
                  <CaretDown size={10} />
                {:else}
                  <ArrowsClockwise size={14} />
                {/if}
              </Popover.Trigger>
              <Popover.Portal>
                <Popover.Content
                  align="end"
                  sideOffset={10}
                  class="z-50 w-72 rounded-2xl border border-border/50 bg-popover/95 p-3 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
                >
                  <p class="text-label mb-2 text-left">Semantic search</p>
                  <div class="space-y-1 mb-3 text-left">
                    {#if embeddingModelId}
                      <p class="text-xs text-muted-foreground">
                        Model <span class="font-mono text-foreground">{embeddingModelId}</span>
                      </p>
                    {/if}
                    <p class="text-xs text-muted-foreground tabular-nums">
                      {embeddedRows.toLocaleString()} of {totalRecords.toLocaleString()} records embedded
                    </p>
                    {#if embeddingsDetail}
                      <p class="text-xs text-warning">{embeddingsDetail}</p>
                    {/if}
                  </div>
                  <div class="flex flex-col gap-1.5">
                    {#if embeddingsStatus === "partial"}
                      <button
                        type="button"
                        onclick={() => runCompute(false)}
                        class="h-9 w-full rounded-lg bg-primary text-primary-foreground text-xs font-bold uppercase tracking-wider hover:bg-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        Update embeddings
                      </button>
                    {/if}
                    <button
                      type="button"
                      onclick={() => runCompute(true)}
                      title="Drop and rebuild the whole embedding space"
                      class="h-9 w-full rounded-lg border border-border bg-background text-xs font-bold uppercase tracking-wider text-muted-foreground hover:bg-accent hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      Recompute
                    </button>
                  </div>
                </Popover.Content>
              </Popover.Portal>
            </Popover.Root>
          {/if}
        </div>
      </div>

      {#if splitFacet.length > 0}
        <FacetSelect
          label="Split"
          values={splitFacet}
          selected={facetSelected("split")}
          onChange={(values) => handleFacetChange("split", values)}
        />
      {/if}
      {#if statusFacet.length > 0}
        <FacetSelect
          label="Status"
          values={statusFacet}
          selected={facetSelected("status")}
          onChange={(values) => handleFacetChange("status", values)}
        />
      {/if}

      <button
        type="button"
        onclick={() => (editorIndex = editorIndex === -1 ? null : -1)}
        class="inline-flex items-center gap-1.5 h-10 px-3.5 rounded-xl border border-border bg-background text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground hover:bg-accent shadow-sm transition-colors shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <FunnelSimple size={15} />
        Filter
        <Plus size={13} />
      </button>
    </div>

    <div class="flex items-center gap-3 shrink-0">
      {#if onViewChange}
        <div
          class="flex items-center rounded-xl border border-border overflow-hidden shadow-sm"
          role="group"
          aria-label="View mode"
        >
          <button
            type="button"
            title="Gallery view"
            aria-label="Gallery view"
            aria-pressed={view === "grid"}
            class="px-3 py-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring {view ===
            'grid'
              ? 'bg-primary text-primary-foreground'
              : 'bg-background text-muted-foreground hover:text-foreground'}"
            onclick={() => onViewChange("grid")}
          >
            <SquaresFour size={16} weight={view === "grid" ? "fill" : "regular"} />
          </button>
          <button
            type="button"
            title="Table view"
            aria-label="Table view"
            aria-pressed={view === "table"}
            class="px-3 py-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring {view ===
            'table'
              ? 'bg-primary text-primary-foreground'
              : 'bg-background text-muted-foreground hover:text-foreground'}"
            onclick={() => onViewChange("table")}
          >
            <Rows size={16} weight={view === "table" ? "fill" : "regular"} />
          </button>
        </div>
      {/if}

      {#if onSortChange && sortableColumns.length > 0}
        <div
          class="flex items-center gap-1"
          title={ranked ? "Results are ranked by similarity" : undefined}
        >
          <Select.Root
            type="single"
            value={sort}
            items={sortItems}
            disabled={ranked}
            onValueChange={(value) => onSortChange(value || undefined, value ? order : undefined)}
          >
            <Select.Trigger
              aria-label="Sort column"
              class="inline-flex h-10 items-center gap-2 px-3.5 rounded-xl border border-border bg-background text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground shadow-sm transition-colors disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {#snippet children()}
                <ArrowsDownUp size={14} />
                <span class="max-w-[120px] truncate">
                  {sort ? formatColumnLabel(sort) : "Sort"}
                </span>
              {/snippet}
            </Select.Trigger>
            <Select.Portal>
              <Select.Content
                sideOffset={8}
                class="z-50 min-w-[11rem] max-h-72 overflow-y-auto rounded-2xl border border-border/50 bg-popover/95 p-1.5 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
              >
                {#each sortItems as item (item.value)}
                  <Select.Item
                    value={item.value}
                    label={item.label}
                    class="cursor-pointer rounded-lg px-2.5 py-1.5 text-sm outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground {sort ===
                    item.value
                      ? 'font-semibold text-primary'
                      : ''}"
                  >
                    {item.label}
                  </Select.Item>
                {/each}
              </Select.Content>
            </Select.Portal>
          </Select.Root>
          {#if sort}
            <button
              type="button"
              onclick={() => onSortChange(sort, order === "desc" ? "asc" : "desc")}
              disabled={ranked}
              aria-label="Toggle sort direction"
              title={order === "desc" ? "Descending" : "Ascending"}
              class="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-background text-muted-foreground hover:text-foreground hover:bg-accent shadow-sm transition-colors disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {#if order === "desc"}
                <SortDescending size={16} />
              {:else}
                <SortAscending size={16} />
              {/if}
            </button>
          {/if}
        </div>
      {/if}

      <!-- Records count -->
      <div
        class="px-3.5 py-1.5 rounded-xl bg-background border border-border flex items-center gap-2.5 shadow-sm"
      >
        <span
          class="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1"
        >
          {#if ranked}
            Ranked
          {:else}
            Records
          {/if}
        </span>
        <span class="text-sm font-black text-primary tabular-nums">{total.toLocaleString()}</span>
      </div>
    </div>
  </div>

  <!-- Row 2 — active filter chips + find-similar mode chip -->
  {#if activeFilters.length > 0 || similarTo}
    <div class="flex flex-wrap items-center gap-1.5">
      {#if similarTo}
        <div
          class="inline-flex items-center gap-1.5 h-7 pl-2.5 pr-1 rounded-full bg-primary text-primary-foreground text-xs shadow-sm"
        >
          <Images size={12} weight="fill" />
          <span class="font-medium">
            Similar to <span class="font-mono">{similarTo}</span>
          </span>
          <button
            type="button"
            onclick={() => onClearSimilar?.()}
            aria-label="Exit find-similar mode"
            class="p-0.5 rounded-full hover:bg-primary-foreground/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-foreground/60"
          >
            <X size={12} />
          </button>
        </div>
      {/if}
      {#each activeFilters as filter, i (i)}
        <div
          class="inline-flex items-center gap-1 h-7 pl-2.5 pr-1 rounded-full border border-primary/30 bg-primary/10 text-xs text-foreground"
        >
          <button
            type="button"
            onclick={() => (editorIndex = editorIndex === i ? null : i)}
            class="font-medium hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
          >
            {chipLabel(filter)}
          </button>
          <button
            type="button"
            onclick={() => removeFilter(i)}
            aria-label="Remove filter"
            class="p-0.5 rounded-full hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X size={12} />
          </button>
        </div>
      {/each}
      {#if activeFilters.length >= 2 || (activeFilters.length >= 1 && (q !== "" || similarTo))}
        <button
          type="button"
          onclick={clearAll}
          class="ml-1 text-xs font-medium text-muted-foreground hover:text-destructive transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm px-1"
        >
          Clear all
        </button>
      {/if}
    </div>
  {/if}

  <!-- Row 3 — compute progress / errors -->
  {#if computing && computeProgress}
    <div class="flex items-center gap-3">
      <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
        {#if computePercent !== null}
          <div
            class="h-full rounded-full bg-primary transition-[width] duration-500"
            style="width: {computePercent}%"
          ></div>
        {:else}
          <div class="h-full w-1/3 animate-pulse rounded-full bg-primary/60"></div>
        {/if}
      </div>
      <span class="shrink-0 text-xs text-muted-foreground tabular-nums">
        {#if computeTotal !== null}
          {computeDone.toLocaleString()} / {computeTotal.toLocaleString()} records
          {#if computePercent !== null}· {computePercent}%{/if}
        {:else}
          Embedding records…
        {/if}
      </span>
    </div>
  {/if}

  {#if computeError}
    <p class="text-xs text-destructive">Embedding computation failed: {computeError}</p>
  {/if}

  {#if searchError && !searchErrorDismissed}
    <div
      class="flex items-center gap-2 px-3 py-2 rounded-lg border border-destructive/30 bg-destructive/10 text-xs text-destructive"
    >
      <Warning size={14} class="shrink-0" />
      <span class="flex-1">{searchError}</span>
      <button
        type="button"
        onclick={() => (searchErrorDismissed = true)}
        aria-label="Dismiss"
        class="p-0.5 rounded-full hover:bg-destructive/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <X size={12} />
      </button>
    </div>
  {/if}

  <!-- Inline filter editor -->
  {#if editorIndex !== null}
    <!-- Remount on target change so the form re-initializes from `initial`. -->
    {#key editorIndex}
      <FilterChipEditor
        {columns}
        initial={editorIndex >= 0 ? activeFilters[editorIndex] : undefined}
        onSave={handleSaveFilter}
        onCancel={() => (editorIndex = null)}
      />
    {/key}
  {/if}
</div>
