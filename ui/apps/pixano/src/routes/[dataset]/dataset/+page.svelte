<script lang="ts">
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";

  import type { DatasetInfo } from "@pixano/core/src";

  import DatasetExplorer from "../../../components/dataset/DatasetExplorer.svelte";

  import { datasetsStore } from "../../../lib/stores/datasetStores";

  let selectedDataset: DatasetInfo;

  $: {
    let currentDatasetName: string;
    page.subscribe((value) => (currentDatasetName = value.params.dataset));
    datasetsStore.subscribe((value) => {
      const foundDataset = value?.find((dataset) => dataset.name === currentDatasetName);
      if (foundDataset) {
        selectedDataset = foundDataset;
      }
    });
  }

  const handleSelectItem = async (event: CustomEvent) => {
    await goto(`/${selectedDataset.name}/dataset/${event.detail}`);
  };
</script>

{#if selectedDataset?.page}
  <div class="pt-20 h-1 min-h-screen">
    <DatasetExplorer {selectedDataset} on:selectItem={(event) => handleSelectItem(event)} />
  </div>
{/if}
