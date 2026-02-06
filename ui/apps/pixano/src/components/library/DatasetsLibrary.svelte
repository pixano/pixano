<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onMount } from "svelte";

  import type { DatasetInfo } from "@pixano/core/src";
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

<div class="max-w-7xl mx-auto py-10 px-6">
  {#if datasets}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {#each datasets as dataset}
        {#if !dataset.isFiltered}
          <DatasetPreviewCard {dataset} on:selectDataset={() => handleSelectDataset(dataset)} />
        {/if}
      {/each}
    </div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
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
