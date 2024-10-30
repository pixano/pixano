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
  import { onDestroy } from "svelte";

  let selectedDatasetId: string;
  let selectedDataset: DatasetBrowser;

  $: page.subscribe((value) => (selectedDatasetId = value.params.dataset));

  $: unsubscribe2datasetTableStore = datasetTableStore.subscribe((pagination) => {
    if (selectedDatasetId) {
      getBrowser(selectedDatasetId, pagination.currentPage, pagination.pageSize, pagination.query)
        .then((datasetItems) => (selectedDataset = datasetItems))
        .catch((err) => console.log("ERROR: Couldn't get dataset items", err));
    }
  });

  const handleSelectItem = async (event: CustomEvent) => {
    await goto(`/${selectedDataset.id}/dataset/${event.detail}`);
  };

  onDestroy(() => {
    unsubscribe2datasetTableStore();
  });
</script>

{#if selectedDataset?.table_data}
  <div class="pt-20 h-1 min-h-screen">
    <DatasetExplorer {selectedDataset} on:selectItem={handleSelectItem} />
  </div>
{/if}
