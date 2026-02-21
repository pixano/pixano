<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  import type { DatasetBrowser } from "$lib/ui";
  import { icons } from "$lib/ui";

  import FilterTable from "./FilterTable.svelte";

  
  interface Props {
    selectedDataset: DatasetBrowser;
    selectedSearchModel: string | undefined;
    searchInput: string;
    onSearch?: (searchInput: string) => void;
    onClearSearch?: () => void;
    onFilter?: (where: string) => void;
  }

  let {
    selectedDataset,
    selectedSearchModel = $bindable(),
    searchInput = $bindable(),
    onSearch,
    onClearSearch,
    onFilter,
  }: Props = $props();
  let filterColumns = $derived(
    (selectedDataset.table_data.columns ?? []).flatMap((col) =>
      col?.name && col?.type ? [{ name: col.name, type: col.type }] : [],
    ),
  );
  const searchModels = $derived(selectedDataset.semantic_search);

  $effect(() => {
    if (!selectedSearchModel && searchModels.length > 0) {
      selectedSearchModel = searchModels[0];
    }
  });

  const handleSearch = () => {
    onSearch?.(searchInput);
  };

  const handleClearSearch = () => {
    onClearSearch?.();
  };

  const handleFilter = (where: string) => {
    onFilter?.(where);
  };
</script>

<div class="ml-auto relative flex items-center py-5 h-20">
  <FilterTable columns={filterColumns} {handleFilter} />
  {#if searchModels.length > 0}
    <select
      class="h-10 px-4 mx-4 border rounded-lg bg-background border-border text-foreground text-sm"
      bind:value={selectedSearchModel}
    >
      {#each searchModels as model}
        <option value={model}>
          {model}
        </option>
      {/each}
    </select>
    <div class="relative flex items-center">
      <input
        type="text"
        bind:value={searchInput}
        placeholder="Semantic search using {selectedSearchModel}"
        class="h-10 pl-10 pr-4 rounded-lg border text-sm text-foreground placeholder-muted-foreground bg-background border-border shadow-sm focus:outline-none focus:ring-2 focus:ring-ring transition-colors"
        onchange={handleSearch}
      />
      <svg
        xmlns="http://www.w3.org/2000/svg"
        height="48"
        viewBox="0 -960 960 960"
        width="48"
        class="absolute left-2 h-5 w-5 text-muted-foreground pointer-events-none"
      >
        <path d={icons.svg_search} fill="currentcolor" />
      </svg>
      {#if searchInput !== ""}
        <button
          class="absolute right-2 p-1 rounded-full transition-colors hover:bg-accent"
          onclick={handleClearSearch}
          aria-label="Clear search"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="h-5 w-5 text-foreground"
          >
            <path d={icons.svg_clear} fill="currentcolor" />
          </svg>
        </button>
      {/if}
    </div>
  {/if}
</div>
