<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { DatasetInfo } from "@pixano/core";
  import pixanoLogo from "@pixano/core/src/assets/pixano.png";
  import { svg_search } from "@pixano/core/src/icons";

  import { datasetFilter, datasetsStore } from "$lib/stores/datasetStores";

  export let datasets: Array<DatasetInfo>;

  const handleSearch = (e: Event) => {
    const target = e.currentTarget as HTMLInputElement;
    datasetFilter.set(target.value);
    datasetsStore.update((value = []) =>
      value.map((dataset) => ({
        ...dataset,
        isFiltered: !dataset.name.toLocaleLowerCase().includes(target.value.toLocaleLowerCase()),
      })),
    );
  };
</script>

<header
  class="p-4 w-full h-fit pt-6 pb-4 px-20 xl:px-60 flex flex-col justify-evenly bg-background border-b border-border font-DM Sans z-10"
>
  <div class="flex gap-3 items-center justify-between">
    <div class="flex gap-3 items-center">
      <img src={pixanoLogo} alt="Logo Pixano" class="w-7 h-7" />
      <span class="text-xl font-semibold text-foreground uppercase tracking-wide">Pixano</span>
    </div>
    {#if datasets}
      <div class="relative flex items-center">
        <input
          id="search-input"
          type="text"
          placeholder="Search datasets..."
          class="h-9 w-64 pl-9 pr-4 rounded-lg bg-muted border border-border
          text-foreground placeholder-muted-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring transition-colors"
          on:input={handleSearch}
          value={$datasetFilter}
        />
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="48"
          viewBox="0 -960 960 960"
          width="48"
          class="absolute left-2.5 h-4 w-4 pointer-events-none"
        >
          <path d={svg_search} fill="hsl(var(--muted-foreground))" />
        </svg>
      </div>
    {/if}
  </div>
  {#if datasets}
    <div class="flex pt-3 w-full items-center flex-wrap gap-3 text-foreground">
      <div class="px-3 py-1.5 rounded-full bg-muted border border-border flex items-center gap-2">
        <span class="text-base font-medium">{datasets?.length}</span>
        <span class="text-sm text-muted-foreground">
          dataset{datasets?.length > 1 ? "s" : ""}
        </span>
      </div>
      <div class="px-3 py-1.5 rounded-full bg-muted border border-border flex items-center gap-2">
        <span class="text-base font-medium">
          {datasets.reduce((sum, dataset) => sum + dataset.num_items, 0)}
        </span>
        <span class="text-sm text-muted-foreground">
          item{datasets.reduce((sum, dataset) => sum + dataset.num_items, 0) > 1 ? "s" : ""}
        </span>
      </div>
    </div>
  {/if}
</header>
