<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onDestroy } from "svelte";

  import type { DatasetBrowser } from "@pixano/core/src";
  import { getBrowser } from "@pixano/core/src/api";

  import DatasetExplorer from "../../../components/dataset/DatasetExplorer.svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { datasetTableStore } from "$lib/stores/datasetStores";

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
  <DatasetExplorer {selectedDataset} on:selectItem={handleSelectItem} />
{/if}
