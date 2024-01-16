<script lang="ts">
  import { Loader2Icon } from "lucide-svelte";
  import { goto } from "$app/navigation";

  import type { DatasetInfo } from "@pixano/core/src";

  import { datasetsStore as datasetsStore } from "../lib/stores/datasetStores";
  import DatasetPreviewCard from "../components/dataset/DatasetPreviewCard.svelte";

  let datasets: DatasetInfo[];

  datasetsStore.subscribe((value) => {
    if (value) {
      datasets = value;
    }
  });

  const handleSelectDataset = async (dataset: DatasetInfo) => {
    await goto(`${dataset.name}/dataset`);
  };
</script>

<svelte:head>
  <title>Pixano</title>
  <meta name="description" content="Pixano app" />
</svelte:head>

<section class="p-8">
  <div class="flex flex-wrap justify-center gap-6 mx-20">
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
</section>
