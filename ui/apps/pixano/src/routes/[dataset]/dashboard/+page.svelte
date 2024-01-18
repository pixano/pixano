<script lang="ts">
  import { page } from "$app/stores";

  import type { DatasetInfo } from "@pixano/core/src";

  import Dashboard from "../../../components/dashboard/Dashboard.svelte";

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
</script>

{#if selectedDataset?.page}
  <div class="pt-20 h-1 min-h-screen">
    <Dashboard {selectedDataset} />
  </div>
{/if}
