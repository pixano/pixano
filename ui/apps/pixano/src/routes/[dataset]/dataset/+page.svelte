<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";

  import type { DatasetBrowser } from "@pixano/core/src";

  import DatasetExplorer from "../../../components/dataset/DatasetExplorer.svelte";
  import { getBrowser } from "@pixano/core/src/api";
  import { datasetTableStore } from "$lib/stores/datasetStores";

  let selectedDatasetId: string;
  let selectedDataset: DatasetBrowser;

  $: page.subscribe((value) => (selectedDatasetId = value.params.dataset));

  $: {
    datasetTableStore.subscribe((pagination) => {
      //prevent api call before selectedId is set.  NOTE: some weird async ordering logic with $ / stores...
      if (selectedDatasetId) {
        // NOTE: WEIRD BUG(?) HERE, this got called more and more often, each time we go back to library
        // number of call increases (when going to a page > 1)
        console.log("BUGLOG 'not once' - datasetTableStore subscribe");
        getBrowser(selectedDatasetId, pagination.currentPage, pagination.pageSize, pagination.query)
          .then((datasetItems) => (selectedDataset = datasetItems))
          .catch((err) => console.log("ERROR: Couldn't get dataset items", err));
      }
      // currentDatasetStore.subscribe((currentDataset) => {
      //   getBrowser(selectedDatasetId, pagination.currentPage, pagination.pageSize).then(
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
    <DatasetExplorer {selectedDataset} on:selectItem={handleSelectItem} />
  </div>
{/if}
