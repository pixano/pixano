<script lang="ts">
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";

  import type { ExplorerData } from "@pixano/core/src";

  import DatasetExplorer from "../../../components/dataset/DatasetExplorer.svelte";
  import { getDatasetItems } from "@pixano/core/src/api";

  let selectedDataset: ExplorerData;
  let currentDatasetId: string;

  $: {
    page.subscribe((value) => (currentDatasetId = value.params.dataset));
    getDatasetItems(currentDatasetId, 1, 20).then((value) => (selectedDataset = value));
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
