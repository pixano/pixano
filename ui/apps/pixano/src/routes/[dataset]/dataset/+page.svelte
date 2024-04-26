<script lang="ts">
  import { goto } from "$app/navigation";

  import type { ExplorerData } from "@pixano/core/src";

  import DatasetExplorer from "../../../components/dataset/DatasetExplorer.svelte";
  import { getDatasetItems } from "@pixano/core/src/api";
  import { currentDatasetStore, datasetTableStore } from "$lib/stores/datasetStores";

  let selectedDataset: ExplorerData;

  $: {
    datasetTableStore.subscribe((pagination) => {
      currentDatasetStore.subscribe((currentDataset) => {
        getDatasetItems(currentDataset.id, pagination.currentPage, pagination.pageSize).then(
          (datasetItems) => (selectedDataset = datasetItems),
        );
      });
    });
  }

  $: {
    // datasetsStore.subscribe((value) => {
    //   const foundDataset = value?.find((dataset) => dataset.name === currentDatasetId);
    //   if (foundDataset) {
    //     selectedDataset = foundDataset;
    //   }
    // });
  }

  const handleSelectItem = async (event: CustomEvent) => {
    await goto(`/${selectedDataset.name}/dataset/${event.detail}`);
  };
</script>

{#if selectedDataset?.table_data}
  <div class="pt-20 h-1 min-h-screen">
    <DatasetExplorer {selectedDataset} on:selectItem={(event) => handleSelectItem(event)} />
  </div>
{/if}
