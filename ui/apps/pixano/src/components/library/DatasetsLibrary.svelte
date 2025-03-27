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
    selectedTool,
  } from "@pixano/dataset-item-workspace/src/lib/stores/datasetItemWorkspaceStores";

  import DatasetPreviewCard from "../../components/dataset/DatasetPreviewCard.svelte";
  import { goto } from "$app/navigation";
  import { currentDatasetStore } from "$lib/stores/datasetStores";

  export let datasets: Array<DatasetInfo>;

  const handleSelectDataset = async (dataset: DatasetInfo) => {
    currentDatasetStore.set(dataset);
    await goto(`${dataset.id}/dataset`);
  };

  onMount(() => {
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
