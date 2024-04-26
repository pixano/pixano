<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */
  import { Loader2Icon } from "lucide-svelte";
  import { goto } from "$app/navigation";
  import type { DatasetInfo } from "@pixano/core/src";
  import DatasetPreviewCard from "../../components/dataset/DatasetPreviewCard.svelte";
  import { currentDatasetStore } from "$lib/stores/datasetStores";

  export let datasets: Array<DatasetInfo>;

  const handleSelectDataset = async (dataset: DatasetInfo) => {
    currentDatasetStore.set(dataset);
    await goto(`${dataset.name}/dataset`);
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
