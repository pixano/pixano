<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onDestroy } from "svelte";

  import type { DatasetInfo } from "@pixano/core/src";

  import Dashboard from "../../../components/dashboard/Dashboard.svelte";
  import { currentDatasetStore } from "$lib/stores/datasetStores";

  let selectedDataset: DatasetInfo;

  $: getDatasetInfo = currentDatasetStore.subscribe(
    (datasetInfo) => (selectedDataset = datasetInfo),
  );

  onDestroy(() => {
    getDatasetInfo();
  });

  //import { afterUpdate } from "svelte";

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

{#if selectedDataset}
  <div class="pt-20 h-1 min-h-screen">
    <Dashboard {selectedDataset} />
  </div>
{/if}
