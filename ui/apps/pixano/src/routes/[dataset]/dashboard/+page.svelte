<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { page } from "$app/stores";

  import type { DatasetInfo } from "@pixano/core";
  //import { api } from "@pixano/core/src";
  import Dashboard from "../../../components/dashboard/Dashboard.svelte";

  import { datasetsStore } from "../../../lib/stores/datasetStores";
  //import { afterUpdate } from "svelte";

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

  // get stats if not already loaded, and allow stats on page refresh

  //TMP: disabled, need a rework following python refactor

  // afterUpdate(async () => {
  //   if (selectedDataset && selectedDataset.stats == undefined) {
  //     const completedDatasetwithStats = await api.getDataset(selectedDataset.id);
  //     if (
  //       completedDatasetwithStats.stats !== undefined &&
  //       completedDatasetwithStats.stats?.length > 0
  //     ) {
  //       selectedDataset.stats = completedDatasetwithStats.stats;
  //     }
  //   }
  // });
</script>

{#if selectedDataset?.page}
  <div class="pt-20 h-1 min-h-screen">
    <Dashboard {selectedDataset} />
  </div>
{/if}
