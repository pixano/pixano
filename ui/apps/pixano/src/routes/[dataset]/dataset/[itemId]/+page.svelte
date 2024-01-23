<script lang="ts">
  import { page } from "$app/stores";
  import { type DatasetItem, type DatasetInfo, PrimaryButton } from "@pixano/core/src";
  import ImageWorkspace from "@pixano/imageworkspace/src/ImageWorkspace.svelte";
  import { api } from "@pixano/core/src";

  import {
    datasetsStore,
    isLoadingNewItemStore,
    modelsStore,
    saveCurrentItemStore,
  } from "../../../../lib/stores/datasetStores";
  import { goto } from "$app/navigation";

  let selectedItem: DatasetItem;
  let selectedDataset: DatasetInfo;
  let models: Array<string>;
  let currentDatasetName: string;
  let currentItemId: string;
  let isLoadingNewItem: boolean = false;
  let canSaveCurrentItem: boolean = false;
  let shouldSaveCurrentItem: boolean = false;
  let noItemFound: boolean = false;

  modelsStore.subscribe((value) => {
    models = value;
  });

  saveCurrentItemStore.subscribe((value) => {
    canSaveCurrentItem = value.canSave;
    shouldSaveCurrentItem = value.shouldSave;
  });

  $: saveCurrentItemStore.update((old) => ({ ...old, canSave: canSaveCurrentItem }));

  const handleSelectItem = (dataset: DatasetInfo, id: string) => {
    if (!dataset || id === selectedItem?.id) return;
    api
      .getDatasetItem(dataset.id, encodeURIComponent(id))
      .then((item) => {
        if (selectedItem?.id !== item.id) {
          selectedItem = item;
        }
        if (Object.keys(item).length === 0) {
          noItemFound = true;
        } else {
          noItemFound = false;
        }
      })
      .then(() => isLoadingNewItemStore.set(false))
      .catch((err) => console.error(err));
  };

  page.subscribe((value) => {
    currentDatasetName = value.params.dataset;
    currentItemId = value.params.itemId;
  });

  datasetsStore.subscribe((value) => {
    const foundDataset = value?.find((dataset) => dataset.name === currentDatasetName);
    if (foundDataset) {
      selectedDataset = foundDataset;
    }
  });

  $: {
    if (currentItemId !== selectedItem?.id) {
      isLoadingNewItemStore.set(true);
      handleSelectItem(selectedDataset, currentItemId);
    }
  }

  $: isLoadingNewItemStore.subscribe((value) => {
    isLoadingNewItem = value;
  });

  async function handleSaveItem(savedItem: DatasetItem) {
    await api.postDatasetItem(selectedDataset.id, savedItem);
    handleSelectItem(selectedDataset, currentItemId);
    saveCurrentItemStore.update((old) => ({ ...old, shouldSave: false }));
  }
</script>

{#if selectedItem && selectedDataset}
  <div class="pt-20 h-1 min-h-screen">
    <ImageWorkspace
      {selectedItem}
      {models}
      currentDatasetId={selectedDataset.id}
      {handleSaveItem}
      isLoading={isLoadingNewItem}
      bind:canSaveCurrentItem
      {shouldSaveCurrentItem}
    />
  </div>
{/if}
{#if !selectedItem && noItemFound}
  <div class="w-full pt-40 text-center flex flex-col gap-5 items-center">
    <p>Current item could not be loaded</p>
    <PrimaryButton on:click={() => goto(`/${currentDatasetName}/dataset`)}
      >Back to dataset</PrimaryButton
    >
  </div>
{/if}
