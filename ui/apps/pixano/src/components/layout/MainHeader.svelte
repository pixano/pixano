<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { DatasetInfo } from "@pixano/core";
  import pixanoLogoWhite from "@pixano/core/src/assets/pixano_white.png";
  import { svg_search } from "@pixano/core/src/icons";

  import { datasetsStore } from "$lib/stores/datasetStores";

  export let datasets: Array<DatasetInfo>;

  const handleSearch = (e: Event) => {
    const target = e.currentTarget as HTMLInputElement;
    datasetsStore.update((value = []) =>
      value.map((dataset) => ({
        ...dataset,
        isFiltered: !dataset.name.toLocaleLowerCase().includes(target.value.toLocaleLowerCase()),
      })),
    );
  };
</script>

<header
  class="p-4 w-full h-fit pt-8 px-20 xl:px-60 flex flex-col justify-evenly bg-primary font-Montserrat z-10"
>
  <div class="flex gap-4 items-center">
    <img src={pixanoLogoWhite} alt="Logo Pixano" class="w-7 h-7" />
    <span class="text-2xl font-semibold text-slate-50 uppercase">Pixano</span>
  </div>
  <div class="flex pt-4 h-36 w-full items-center flex-wrap text-slate-50">
    {#if datasets}
      <div class="my-4 mr-8 p-4 pr-8 border rounded-lg border-primary-foreground">
        <span class="mr-2 text-4xl font-medium">{datasets?.length}</span>
        <span class="text-xl font-medium">
          dataset{datasets?.length > 1 ? "s" : ""}
        </span>
      </div>
      <div class="my-4 mr-8 p-4 pr-8 border rounded-lg border-primary-foreground">
        <span class="mr-2 text-4xl font-medium">
          {datasets.reduce((sum, dataset) => sum + dataset.num_items, 0)}
        </span>
        <span class="text-xl font-medium">
          item{datasets.reduce((sum, dataset) => sum + dataset.num_items, 0) > 1 ? "s" : ""}
        </span>
      </div>
      <div class="grow self-end flex flex-row justify-end items-end">
        <div class="flex items-center space-x-2">
          <div class="h-20 relative flex items-center">
            <input
              id="search-input"
              type="text"
              placeholder="Search datasets"
              class="h-10 pl-10 pr-4 rounded border border-primary-foreground bg-primary-foreground
              text-white placeholder-white font-medium focus:outline-none"
              on:input={handleSearch}
            />
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="48"
              viewBox="0 -960 960 960"
              width="48"
              class="absolute left-3 h-5 w-5 pointer-events-none"
            >
              <path d={svg_search} fill="white" />
            </svg>
          </div>
        </div>
      </div>
    {/if}
  </div>
</header>
