<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Loader2Icon } from "lucide-svelte";
  import { goto } from "$app/navigation";
  import type { DatasetInfo } from "@pixano/core/src";
  import DatasetPreviewCard from "../../components/dataset/DatasetPreviewCard.svelte";
  import { currentDatasetStore } from "$lib/stores/datasetStores";

  export let datasets: Array<DatasetInfo>;

  const handleSelectDataset = async (dataset: DatasetInfo) => {
    currentDatasetStore.set(dataset);
    await goto(`${dataset.id}/dataset`);
  };
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
