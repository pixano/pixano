<script lang="ts">
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";

  import type { ExplorerData } from "@pixano/core/src";

  import DatasetExplorer from "../../../components/dataset/DatasetExplorer.svelte";
  import { getDatasetItems } from "@pixano/core/src/api";
  import { currentDatasetStore, datasetTableStore } from "$lib/stores/datasetStores";

  let selectedDatasetId: string;
  let selectedDataset: ExplorerData;

  $: page.subscribe((value) => (selectedDatasetId = value.params.dataset));

  $: {
    datasetTableStore.subscribe((pagination) => {
      //prevent api call before selectedId is set.  NOTE: some weird async ordering logic with $ / stores...
      if (selectedDatasetId) {
        // NOTE: WEIRD BUG(?) HERE, this got called more and more often, each time we go back to library
        // number of call increases (when going to a page > 1)
        console.log("Once????");
        getDatasetItems(selectedDatasetId, pagination.currentPage, pagination.pageSize).then(
          (datasetItems) => (selectedDataset = datasetItems),
        );
      }
      // currentDatasetStore.subscribe((currentDataset) => {
      //   getDatasetItems(selectedDatasetId, pagination.currentPage, pagination.pageSize).then(
      //     (datasetItems) => (selectedDataset = datasetItems),
      //   );
      // });
    });
  }

  // $: {
  //   datasetsStore.subscribe((value) => {
  //     const foundDataset = value?.find((dataset) => dataset.name === currentDatasetId);
  //     if (foundDataset) {
  //       selectedDataset = foundDataset;
  //     }
  //   });
  // }

  const handleSelectItem = async (event: CustomEvent) => {
    await goto(`/${selectedDataset.id}/dataset/${event.detail}`);
  };
</script>

{#if selectedDataset?.table_data}
  <div class="pt-20 h-1 min-h-screen">
    <DatasetExplorer {selectedDataset} on:selectItem={(event) => handleSelectItem(event)} />
  </div>
{/if}
