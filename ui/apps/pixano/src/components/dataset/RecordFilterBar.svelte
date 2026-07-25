<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CircleNotch, FunnelSimple, MagnifyingGlass, Plus, Sparkle, X } from "phosphor-svelte";

  import FilterChipEditor from "./FilterChipEditor.svelte";
  import type { FilterSchemaResponse } from "$lib/api/restTypes";
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
    semanticActive?: boolean;
    computing?: boolean;
    onApply: (updates: { filter?: string[]; q?: string; semantic?: boolean }) => void;
    onCompute?: () => void;
  }

  let {
    filterSchema,
    filters,
    q,
    total,
    semanticActive = false,
    computing = false,
    onApply,
    onCompute,
  }: Props = $props();

  const columns = $derived(filterSchema.columns);
  const hasSearchable = $derived(columns.some((c) => c.searchable));
  const semanticAvailable = $derived((filterSchema.search?.modes ?? []).includes("semantic"));

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

  function submitSearch() {
    const text = searchInput.trim();
    onApply({ q: text || undefined, semantic: semanticMode && text !== "" });
  }

  function clearSearch() {
    searchInput = "";
    onApply({ q: undefined, semantic: false });
  }

  function toggleSemantic() {
    semanticMode = !semanticMode;
    // Re-run the current query in the new mode when there is one.
    if (searchInput.trim() !== "") submitSearch();
    else if (semanticActive) onApply({ semantic: false });
  }

  function chipLabel(filter: RecordFilter): string {
    const op = OPERATOR_LABELS[filter.op] ?? filter.op;
    const value = isListOperator(filter.op) ? filter.values.join(", ") : (filter.values[0] ?? "");
    return `${filter.col} ${op} ${value}`;
  }
</script>

<div class="flex flex-col gap-2 py-3">
  <div class="flex flex-wrap items-center gap-2">
    {#if hasSearchable || semanticAvailable}
      <div class="relative flex items-center">
        {#if semanticMode}
          <Sparkle size={16} class="absolute left-2.5 text-primary pointer-events-none" />
        {:else}
          <MagnifyingGlass
            size={16}
            class="absolute left-2.5 text-muted-foreground pointer-events-none"
          />
        {/if}
        <input
          type="text"
          bind:value={searchInput}
          onkeydown={(e) => e.key === "Enter" && submitSearch()}
          placeholder={semanticMode ? "Search by meaning…" : "Search text…"}
          class="h-9 w-72 pl-8 pr-8 rounded-lg border bg-background text-sm text-foreground placeholder-muted-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring {semanticMode
            ? 'border-primary/50'
            : 'border-border'}"
        />
        {#if searchInput !== ""}
          <button
            type="button"
            onclick={clearSearch}
            aria-label="Clear search"
            class="absolute right-2 p-0.5 rounded-full hover:bg-accent"
          >
            <X size={14} />
          </button>
        {/if}
      </div>

      {#if semanticAvailable}
        <button
          type="button"
          onclick={toggleSemantic}
          title="Toggle semantic (meaning-based) search"
          class="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg border text-sm shadow-sm {semanticMode
            ? 'border-primary bg-primary/10 text-primary'
            : 'border-border bg-background text-foreground hover:bg-accent'}"
        >
          <Sparkle size={16} weight={semanticMode ? "fill" : "regular"} />
          Semantic
        </button>
      {:else if onCompute}
        <button
          type="button"
          onclick={onCompute}
          disabled={computing}
          title="Compute embeddings to enable semantic search"
          class="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg border border-dashed border-border bg-background text-sm text-muted-foreground hover:bg-accent shadow-sm disabled:opacity-60"
        >
          {#if computing}
            <CircleNotch size={16} class="animate-spin" />
            Computing…
          {:else}
            <Sparkle size={16} />
            Enable semantic search
          {/if}
        </button>
      {/if}
    {/if}

    <button
      type="button"
      onclick={() => (editorIndex = editorIndex === -1 ? null : -1)}
      class="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg border border-border bg-background text-sm text-foreground hover:bg-accent shadow-sm"
    >
      <FunnelSimple size={16} />
      Add filter
      <Plus size={14} />
    </button>

    <span class="ml-auto text-sm text-muted-foreground tabular-nums">
      {#if semanticActive}
        <span class="text-primary">Ranked by similarity ·</span>
      {/if}
      {total.toLocaleString()}
      {total === 1 ? "record" : "records"}
    </span>
  </div>

  {#if activeFilters.length > 0}
    <div class="flex flex-wrap items-center gap-1.5">
      {#each activeFilters as filter, i (i)}
        <div
          class="inline-flex items-center gap-1 h-7 pl-2.5 pr-1 rounded-full border border-primary/30 bg-primary/10 text-xs text-foreground"
        >
          <button
            type="button"
            onclick={() => (editorIndex = editorIndex === i ? null : i)}
            class="font-medium hover:underline"
          >
            {chipLabel(filter)}
          </button>
          <button
            type="button"
            onclick={() => removeFilter(i)}
            aria-label="Remove filter"
            class="p-0.5 rounded-full hover:bg-primary/20"
          >
            <X size={12} />
          </button>
        </div>
      {/each}
    </div>
  {/if}

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
