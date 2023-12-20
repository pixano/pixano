<script lang="ts">
  import { goto } from "$app/navigation";

  import type { DatasetInfo } from "@pixano/core/src";
  import DatasetPreviewCard from "@pixano/core/src/DatasetPreviewCard.svelte";
  import { datasetsStore as datasetsStore } from "../lib/stores/datasetStores";

  let datasets: DatasetInfo[] = [];

  datasetsStore.subscribe((value) => {
    if (value) {
      datasets = value;
    }
  });

  const handleSelectDataset = async (dataset: DatasetInfo) => {
    await goto(`${dataset.name}/dataset`);
  };

  $: console.log({ datasets });
</script>

<svelte:head>
  <title>Pixano</title>
  <meta name="description" content="Pixano app" />
</svelte:head>

<section class="p-8">
  <div class="flex flex-wrap justify-center gap-6 mx-20">
    {#each datasets as dataset}
      <!-- {#if dataset.name.toUpperCase().includes(filter.toUpperCase())} -->
      <DatasetPreviewCard {dataset} on:selectDataset={() => handleSelectDataset(dataset)} />
      <!-- {/if} -->
    {/each}
  </div>
</section>
