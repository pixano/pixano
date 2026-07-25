<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { FunnelSimple, MagnifyingGlass, Plus, X } from "phosphor-svelte";

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
    onApply: (updates: { filter?: string[]; q?: string }) => void;
  }

  let { filterSchema, filters, q, total, onApply }: Props = $props();

  const columns = $derived(filterSchema.columns);
  const hasSearchable = $derived(columns.some((c) => c.searchable));

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
    onApply({ q: searchInput.trim() || undefined });
  }

  function clearSearch() {
    searchInput = "";
    onApply({ q: undefined });
  }

  function chipLabel(filter: RecordFilter): string {
    const op = OPERATOR_LABELS[filter.op] ?? filter.op;
    const value = isListOperator(filter.op) ? filter.values.join(", ") : (filter.values[0] ?? "");
    return `${filter.col} ${op} ${value}`;
  }
</script>

<div class="flex flex-col gap-2 py-3">
  <div class="flex flex-wrap items-center gap-2">
    {#if hasSearchable}
      <div class="relative flex items-center">
        <MagnifyingGlass
          size={16}
          class="absolute left-2.5 text-muted-foreground pointer-events-none"
        />
        <input
          type="text"
          bind:value={searchInput}
          onkeydown={(e) => e.key === "Enter" && submitSearch()}
          placeholder="Search text…"
          class="h-9 w-64 pl-8 pr-8 rounded-lg border border-border bg-background text-sm text-foreground placeholder-muted-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
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
