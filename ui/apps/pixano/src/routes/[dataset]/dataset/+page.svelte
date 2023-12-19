<script lang="ts">
  import { page } from "$app/stores";
  import { api } from "@pixano/core/src";
  import type { DatasetInfo } from "@pixano/core/src";

  import DatasetExplorer from "../../../components/dataset/DatasetExplorer.svelte";

  import { datasets } from "../../../lib/stores/datasetStores";

  let currentDatasetInfos: DatasetInfo;
  let selectedDataset: DatasetInfo;
  let selectedTab: string = "database";

  $: {
    let currentDatasetName: string;
    page.subscribe((value) => (currentDatasetName = value.params.dataset));
    datasets.subscribe((value) => {
      const foundDataset = value?.find((dataset) => dataset.name === currentDatasetName);
      if (foundDataset) {
        currentDatasetInfos = foundDataset;
      }
    });
    // console.log({ currentDatasetInfos });
  }

  $: {
    console.log("salut");
  }

  $: {
    if (currentDatasetInfos?.id) {
      api
        .getDatasetItems(currentDatasetInfos?.id, 1)
        .then((datasetItems) => {
          selectedDataset = { ...currentDatasetInfos, page: datasetItems };
        })
        .catch((e) => console.error("error", e));
    }
  }
</script>

{#if selectedDataset}
  <DatasetExplorer
    bind:selectedTab
    {selectedDataset}
    currentPage={1}
    on:selectItem={(event) => console.log(event)}
  />
  <!-- on:selectItem={(event) => handleSelectItem(event.detail)} -->
{/if}
