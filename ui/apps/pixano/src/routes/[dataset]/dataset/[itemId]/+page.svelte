<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { page } from "$app/stores";
  import {
    type DatasetItem,
    type DatasetInfo,
    type DatasetItemSave,
    Image,
    PrimaryButton,
    SequenceFrame,
  } from "@pixano/core/src";
  import DatasetItemWorkspace from "@pixano/dataset-item-workspace/src/DatasetItemWorkspace.svelte";
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
  let currentDatasetId: string;
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
    if (!dataset) return;
    api.getDataset(dataset.id).then((ds) => {
      api
        .getDatasetItem(dataset.id, encodeURIComponent(id))
        .then((item) => {
          let item_type: "image"|"video"|"3d" = "image";
          //append /data/<dataset_path>/media url to all urls
          //NOTE: slice(-2) is not very safe, it suppose we respect the ""<dataset_path>/media" rule
          //but as ds.media_dir is an absolute path, we need to make this assumption...
          //Note2: we will need to revert this when we POST/PUT views !!
          const media_dir = "data/" + ds.media_dir.split("/").slice(-2).join("/") + "/";
          Object.values(item.views).map((view) => {
            if (Array.isArray(view)) {
              const video = view as SequenceFrame[];
              item_type = "video"
              video.forEach((sf)=> {
                sf.data.type = "video";
                sf.data.url = media_dir + sf.data.url;
              });
              video.sort((a, b)=> (a.data.frame_index - b.data.frame_index));
            } else {
              const image = view as Image;
              image.data.type = "image";
              image.data.url = media_dir + image.data.url;
            }
            return view;
          });
          selectedItem = item;
          selectedItem.type = item_type;
          selectedItem.datasetId = dataset.id;
          if (Object.keys(item).length === 0) {
            noItemFound = true;
          } else {
            noItemFound = false;
          }
          console.log("XXX handleSelectIem - selectedItem:", selectedItem);
        })
        .then(() => isLoadingNewItemStore.set(false))
        .catch((err) => console.error(err));
    });
  };

  page.subscribe((value) => {
    currentDatasetId = value.params.dataset;
    currentItemId = value.params.itemId;
  });

  datasetsStore.subscribe((value) => {
    const foundDataset = value?.find((dataset) => dataset.id === currentDatasetId);
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

  async function handleSaveItem(savedItem: DatasetItemSave) {
    await api.postDatasetItem(selectedDataset.id, savedItem);
    handleSelectItem(selectedDataset, currentItemId);
    saveCurrentItemStore.update((old) => ({ ...old, shouldSave: false }));
  }
</script>

{#if selectedItem && selectedDataset}
  <div class="pt-20 h-1 min-h-screen">
    <DatasetItemWorkspace
      {selectedItem}
      {models}
      featureValues={{ main: {}, objects: {} }}
      {handleSaveItem}
      isLoading={isLoadingNewItem}
      bind:canSaveCurrentItem
      {shouldSaveCurrentItem}
      headerHeight={80}
    />
  </div>
{/if}
{#if !selectedItem && noItemFound}
  <div class="w-full pt-40 text-center flex flex-col gap-5 items-center">
    <p>Current item could not be loaded</p>
    <PrimaryButton on:click={() => goto(`/${currentDatasetId}/dataset`)}>
      Back to dataset
    </PrimaryButton>
  </div>
{/if}
