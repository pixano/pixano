<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  import { createEventDispatcher } from "svelte";

  import type { DatasetBrowser } from "@pixano/core/src";
  import { svg_clear, svg_search } from "@pixano/core/src/icons";

  import FilterTable from "./filterTable.svelte";

  // Exports
  export let selectedDataset: DatasetBrowser;
  export let selectedSearchModel: string | undefined;
  export let searchInput: string;

  const searchModels: string[] = [];
  if (selectedDataset.semantic_search.length > 0) {
    for (const model of selectedDataset.semantic_search) {
      // Initialize selected search model
      if (!selectedSearchModel) {
        selectedSearchModel = model;
      }
      searchModels.push(model);
    }
  }

  const dispatch = createEventDispatcher();

  const handleSearch = () => {
    dispatch("search", searchInput);
  };

  const handleClearSearch = () => {
    dispatch("clearSearch");
  };

  const handleFilter = (where: string) => {
    dispatch("filter", where);
  };
</script>

<div class="ml-auto relative flex items-center py-5 h-20">
  <FilterTable columns={selectedDataset.table_data.columns} {handleFilter} />
  {#if searchModels.length > 0}
    <select class="h-10 px-4 mx-4 border rounded bg-slate-50 border-slate-300">
      {#each searchModels as model}
        <option value={selectedSearchModel}>
          {model}
        </option>
      {/each}
    </select>
    <div class="relative flex items-center">
      <input
        type="text"
        bind:value={searchInput}
        placeholder="Semantic search using {selectedSearchModel}"
        class="h-10 pl-10 pr-4 rounded-full border text-slate-800 placeholder-slate-500 bg-slate-50 border-slate-300 shadow-slate-300 accent-main"
        on:change={handleSearch}
      />
      <svg
        xmlns="http://www.w3.org/2000/svg"
        height="48"
        viewBox="0 -960 960 960"
        width="48"
        class="absolute left-2 h-5 w-5 text-slate-800 pointer-events-none"
      >
        <path d={svg_search} fill="currentcolor" />
      </svg>
      {#if searchInput !== ""}
        <button
          class="absolute right-2 p-1 rounded-full transition-colors hover:bg-slate-300"
          on:click={handleClearSearch}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="h-5 w-5 text-slate-800"
          >
            <path d={svg_clear} fill="currentcolor" />
          </svg>
        </button>
      {/if}
    </div>
  {/if}
</div>
