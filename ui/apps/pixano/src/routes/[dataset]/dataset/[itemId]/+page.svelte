<script lang="ts">
  import { page } from "$app/stores";
  import type { DatasetItem, DatasetInfo } from "@pixano/core/src";
  import ImageWorkspace from "@pixano/imageworkspace/src/ImageWorkspace.svelte";
  import { api } from "@pixano/core/src";

  import {
    datasetsStore,
    isLoadingNewItemStore,
    modelsStore,
  } from "../../../../lib/stores/datasetStores";

  let selectedItem: DatasetItem;
  let selectedDataset: DatasetInfo;
  let models: Array<string>;
  let currentDatasetName: string;
  let currentItemId: string;
  let isLoadingNewItem: boolean = false;

  modelsStore.subscribe((value) => {
    models = value;
  });

  const handleSelectItem = (dataset: DatasetInfo, id: string) => {
    api
      .getDatasetItem(dataset.id, encodeURIComponent(id))
      .then((item) => {
        selectedItem = item;
      })
      .then(() => isLoadingNewItemStore.set(false))
      .catch((err) => console.error(err));
  };

  page.subscribe((value) => {
    currentDatasetName = value.params.dataset;
    currentItemId = value.params.itemId;
  });

  $: datasetsStore.subscribe((value) => {
    const foundDataset = value?.find((dataset) => dataset.name === currentDatasetName);
    if (foundDataset && currentItemId) {
      selectedDataset = foundDataset;
      isLoadingNewItemStore.set(true);
      handleSelectItem(selectedDataset, currentItemId);
    }
  });

  $: isLoadingNewItemStore.subscribe((value) => {
    isLoadingNewItem = value;
  });

  async function handleSaveItem(savedItem: DatasetItem) {
    await api.postDatasetItem(selectedDataset.id, savedItem);
    handleSelectItem(selectedDataset, currentItemId);
  }
</script>

{#if selectedItem}
  <ImageWorkspace
    {selectedItem}
    currentDatasetId={selectedDataset.id}
    {models}
    {handleSaveItem}
    isLoading={isLoadingNewItem}
  />
{/if}
