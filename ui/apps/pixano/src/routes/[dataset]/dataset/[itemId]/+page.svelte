<script lang="ts">
  import { page } from "$app/stores";
  import type { DatasetItem, DatasetInfo } from "@pixano/core/src";
  import ImageWorkspace from "@pixano/imageworkspace/src/App.svelte";
  import { api } from "@pixano/core/src";

  import { datasetsStore, modelsStore } from "../../../../lib/stores/datasetStores";

  let selectedItem: DatasetItem;
  let selectedDataset: DatasetInfo;
  let models: Array<string>;
  let currentDatasetName: string;
  let currentItemId: string;

  modelsStore.subscribe((value) => {
    models = value;
  });

  const handleSelectItem = (dataset: DatasetInfo, id: string) => {
    api
      .getDatasetItem(dataset.id, encodeURIComponent(id))
      .then((item) => {
        selectedItem = item;
      })
      .catch((err) => console.error(err));
  };

  page.subscribe((value) => {
    currentDatasetName = value.params.dataset;
    currentItemId = value.params.itemId;

    datasetsStore.subscribe((value) => {
      const foundDataset = value?.find((dataset) => dataset.name === currentDatasetName);
      if (foundDataset && currentItemId) {
        selectedDataset = foundDataset;
        console.log("about to save", { selectedDataset, currentItemId });
        handleSelectItem(selectedDataset, currentItemId);
      }
    });
  });

  async function handleSaveItem(savedItem: DatasetItem) {
    await api.postDatasetItem(selectedDataset.id, savedItem);
    handleSelectItem(selectedDataset, currentItemId);
  }
</script>

{#if selectedItem}
  <ImageWorkspace {selectedItem} {selectedDataset} {models} {handleSaveItem} />
{/if}
