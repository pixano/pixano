<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    ArrowsDownUp,
    CircleNotch,
    FunnelSimple,
    MagnifyingGlass,
    Plus,
    SortAscending,
    SortDescending,
    Sparkle,
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
    onApply: (updates: { filter?: string[]; q?: string; semantic?: boolean }) => void;
    onSortChange?: (sort: string | undefined, order: string | undefined) => void;
    onCompute?: () => void;
    onClearSimilar?: () => void;
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
    onApply,
    onSortChange,
    onCompute,
    onClearSimilar,
  }: Props = $props();

  const columns = $derived(filterSchema.columns);
  const hasSearchable = $derived(columns.some((c) => c.searchable));
  const semanticAvailable = $derived((filterSchema.search?.modes ?? []).includes("semantic"));
  const sortableColumns = $derived(columns.filter((c) => c.sortable));
  const ranked = $derived(semanticActive || similarTo !== "");
  const sortItems = $derived([
    { value: "", label: "Default order" },
    ...sortableColumns.map((c) => ({ value: c.name, label: formatColumnLabel(c.name) })),
  ]);

  // Semantic mode is a local toggle; it activates on submit and reflects the URL state.
  let semanticMode = $state(false);
  $effect(() => {
    semanticMode = semanticActive;
  });

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
    const text = searchInput.trim();
    onApply({ q: text || undefined, semantic: semanticMode && text !== "" });
  }

  function clearSearch() {
    searchInput = "";
    onApply({ q: undefined, semantic: false });
  }

  function setMode(semantic: boolean) {
    if (semanticMode === semantic) return;
    semanticMode = semantic;
    // Re-run the current query in the new mode when there is one.
    if (searchInput.trim() !== "") submitSearch();
    else if (semanticActive) onApply({ semantic: false });
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

  const segmentedButtonClass = (active: boolean) =>
    `px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring ${
      active
        ? "bg-primary text-primary-foreground"
        : "bg-background text-muted-foreground hover:text-foreground"
    }`;
</script>

<div class="flex flex-col gap-2.5 py-3">
  <!-- Row 1 — search, mode, facets, filters · sort, count -->
  <div class="flex items-center justify-between gap-4 flex-wrap">
    <div class="flex items-center gap-3 flex-1 min-w-0 flex-wrap">
      {#if hasSearchable || semanticAvailable}
        <div class="relative group flex-1 min-w-[220px] max-w-md">
          {#if semanticMode}
            <Sparkle
              size={16}
              class="absolute left-3.5 top-1/2 -translate-y-1/2 text-primary pointer-events-none"
            />
          {:else}
            <MagnifyingGlass
              size={16}
              class="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground/60 group-focus-within:text-primary transition-colors pointer-events-none"
            />
          {/if}
          <input
            type="text"
            bind:value={searchInput}
            onkeydown={(e) => e.key === "Enter" && submitSearch()}
            placeholder={semanticMode ? "Search by meaning…" : "Search text…"}
            class="h-10 w-full pl-10 pr-8 rounded-xl bg-muted/50 border text-sm text-foreground placeholder-muted-foreground/60 shadow-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:bg-background {semanticMode
              ? 'border-primary/40'
              : 'border-border'}"
          />
          {#if searchInput !== ""}
            <button
              type="button"
              onclick={clearSearch}
              aria-label="Clear search"
              class="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded-full hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <X size={14} />
            </button>
          {/if}
        </div>

        {#if semanticAvailable}
          <div
            class="flex items-center rounded-xl border border-border overflow-hidden shadow-sm shrink-0"
            role="group"
            aria-label="Search mode"
          >
            <button
              type="button"
              class={segmentedButtonClass(!semanticMode)}
              aria-pressed={!semanticMode}
              onclick={() => setMode(false)}
            >
              Text
            </button>
            <button
              type="button"
              class={segmentedButtonClass(semanticMode)}
              aria-pressed={semanticMode}
              onclick={() => setMode(true)}
            >
              Semantic
            </button>
          </div>
        {:else if onCompute}
          <button
            type="button"
            onclick={onCompute}
            disabled={computing}
            title="Compute embeddings to enable semantic search"
            class="inline-flex items-center gap-1.5 h-10 px-3.5 rounded-xl border border-dashed border-border bg-background text-xs font-bold uppercase tracking-wider text-muted-foreground hover:bg-accent hover:text-foreground shadow-sm transition-colors disabled:opacity-60 shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {#if computing}
              <CircleNotch size={15} class="animate-spin" />
              Computing…
            {:else}
              <Sparkle size={15} />
              Enable semantic search
            {/if}
          </button>
        {/if}
      {/if}

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
            <Sparkle size={12} class="text-primary" />
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
          <Sparkle size={12} weight="fill" />
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
