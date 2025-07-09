<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Loader2Icon } from "lucide-svelte";
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
  import { currentDatasetStore } from "$lib/stores/datasetStores";

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

<div class="flex flex-wrap justify-center gap-6 py-12">
  {#if datasets}
    {#each datasets as dataset}
      {#if !dataset.isFiltered}
        <DatasetPreviewCard {dataset} on:selectDataset={() => handleSelectDataset(dataset)} />
      {/if}
    {/each}
  {:else}
    <Loader2Icon class="animate-spin" />
  {/if}
</div>
