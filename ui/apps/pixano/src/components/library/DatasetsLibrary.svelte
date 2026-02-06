<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onMount } from "svelte";

  import type { DatasetInfo } from "@pixano/core/src";
  import { svg_search } from "@pixano/core/src/icons";
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

<div class="flex flex-col gap-6">
  <!-- Toolbar: search + stats -->
  <div class="flex items-center justify-between gap-4 flex-wrap">
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
    {#if datasets}
      <div class="flex items-center gap-3">
        <div class="px-3 py-1 rounded-full bg-muted border border-border flex items-center gap-2">
          <span class="text-sm font-medium">{datasets.length}</span>
          <span class="text-xs text-muted-foreground">
            dataset{datasets.length > 1 ? "s" : ""}
          </span>
        </div>
        <div class="px-3 py-1 rounded-full bg-muted border border-border flex items-center gap-2">
          <span class="text-sm font-medium">
            {datasets.reduce((sum, dataset) => sum + dataset.num_items, 0)}
          </span>
          <span class="text-xs text-muted-foreground">
            item{datasets.reduce((sum, dataset) => sum + dataset.num_items, 0) > 1 ? "s" : ""}
          </span>
        </div>
      </div>
    {/if}
  </div>

  <!-- Dataset grid -->
  {#if datasets}
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
      {#each datasets as dataset}
        {#if !dataset.isFiltered}
          <DatasetPreviewCard {dataset} on:selectDataset={() => handleSelectDataset(dataset)} />
        {/if}
      {/each}
    </div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
      {#each Array(4) as _}
        <div class="h-72 rounded-xl border border-border bg-card animate-pulse">
          <div class="pt-4 px-4 space-y-2">
            <div class="h-5 w-2/3 bg-muted rounded"></div>
            <div class="h-4 w-1/3 bg-muted rounded"></div>
          </div>
          <div class="m-4 h-[150px] bg-muted rounded-lg"></div>
        </div>
      {/each}
    </div>
  {/if}
</div>
