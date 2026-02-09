<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onMount } from "svelte";

  import type { DatasetInfo } from "@pixano/core";
  import { icons } from "@pixano/core";
  import { panTool } from "@pixano/dataset-item-workspace/src/lib/settings/selectionTools";
  import {
    modelsUiStore,
    resetColorScale,
    selectedTool,
  } from "@pixano/dataset-item-workspace/src/lib/stores/datasetItemWorkspaceStores";

  import DatasetPreviewCard from "../../components/dataset/DatasetPreviewCard.svelte";
  import { goto } from "$app/navigation";
  import {
    currentDatasetStore,
    datasetFilter,
    datasetsStore,
    datasetTableStore,
    defaultDatasetTableValues,
  } from "$lib/stores/datasetStores";

  /**
   * DatasetsLibrary Component
   *
   * This component displays a list of datasets. Each dataset is represented by a
   * DatasetPreviewCard component. When a dataset is selected, the user is navigated
   * to the dataset's detail page.
   *
   * Props:
   *   - datasets: Array<DatasetInfo> - An array of dataset information objects.
   *
   * Events:
   *   - selectDataset: Triggered when a dataset is selected.
   */

  export let datasets: Array<DatasetInfo>;

  const handleSelectDataset = async (dataset: DatasetInfo) => {
    currentDatasetStore.set(dataset);
    datasetTableStore.set(defaultDatasetTableValues);
    await goto(`${dataset.id}/dataset`);
  };

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

  onMount(() => {
    resetColorScale();
    //reset interactive segmentation model & table
    modelsUiStore.set({
      currentModalOpen: "none",
      selectedModelName: "",
      selectedTableName: "",
      yetToLoadEmbedding: true,
    });
    //reset Tool
    selectedTool.set(panTool);
  });
</script>

<div class="flex flex-col gap-8">
  <!-- Toolbar: search + stats -->
  <div class="flex items-center justify-between gap-6 flex-wrap pb-2 border-b border-border/50">
    <div class="relative flex items-center group">
      <input
        id="search-input"
        type="text"
        placeholder="Search datasets..."
        class="h-10 w-72 pl-10 pr-4 rounded-xl bg-muted/50 border border-border
        text-foreground placeholder-muted-foreground/60 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:bg-background transition-all duration-200 shadow-sm"
        on:input={handleSearch}
        value={$datasetFilter}
      />
      <svg
        xmlns="http://www.w3.org/2000/svg"
        height="48"
        viewBox="0 -960 960 960"
        width="48"
        class="absolute left-3.5 h-4 w-4 pointer-events-none text-muted-foreground/60 group-focus-within:text-primary transition-colors"
      >
        <path d={icons.svg_search} fill="currentColor" />
      </svg>
    </div>
    {#if datasets}
      <div class="flex items-center gap-4">
        <div
          class="px-3.5 py-1.5 rounded-xl bg-background border border-border flex items-center gap-2.5 shadow-sm"
        >
          <span class="text-xs font-bold text-muted-foreground uppercase tracking-wider">
            Datasets
          </span>
          <span class="text-sm font-black text-primary tabular-nums">
            {datasets.length}
          </span>
        </div>
        <div
          class="px-3.5 py-1.5 rounded-xl bg-background border border-border flex items-center gap-2.5 shadow-sm"
        >
          <span class="text-xs font-bold text-muted-foreground uppercase tracking-wider">
            Total Items
          </span>
          <span class="text-sm font-black text-primary tabular-nums">
            {datasets.reduce((sum, dataset) => sum + dataset.num_items, 0)}
          </span>
        </div>
      </div>
    {/if}
  </div>

  <!-- Dataset grid -->
  {#if datasets}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {#each datasets as dataset}
        {#if !dataset.isFiltered}
          <div class="animate-in fade-in slide-in-from-bottom-2 duration-500">
            <DatasetPreviewCard {dataset} on:selectDataset={() => handleSelectDataset(dataset)} />
          </div>
        {/if}
      {/each}
    </div>
  {:else}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {#each [0, 1, 2, 3, 4, 5, 6, 7] as i (i)}
        <div
          class="flex flex-col rounded-2xl border border-border/60 bg-card animate-pulse overflow-hidden"
        >
          <div class="aspect-video bg-muted/50 w-full"></div>
          <div class="p-5 space-y-4">
            <div class="space-y-2">
              <div class="h-4 w-2/3 bg-muted rounded-full"></div>
            </div>
            <div class="space-y-2">
              <div class="h-2 w-full bg-muted/40 rounded-full"></div>
              <div class="h-2 w-4/5 bg-muted/40 rounded-full"></div>
            </div>
            <div class="pt-4 border-t border-border/40 flex gap-4">
              <div class="h-3 w-12 bg-muted/50 rounded-full"></div>
              <div class="h-3 w-12 bg-muted/50 rounded-full"></div>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
