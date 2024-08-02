<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { ItemObject, DatasetItem, FeaturesValues, DatasetItemSave } from "@pixano/core";

  import Toolbar from "./components/Toolbar.svelte";
  import Inspector from "./components/Inspector/InspectorInspector.svelte";
  import LoadModelModal from "./components/LoadModelModal.svelte";
  import {
    itemObjects,
    itemMetas,
    newShape,
    canSave,
    saveData,
  } from "./lib/stores/datasetItemWorkspaceStores";
  import "./index.css";
  import type { Embeddings } from "./lib/types/datasetItemWorkspaceTypes";
  import DatasetItemViewer from "./components/DatasetItemViewer/DatasetItemViewer.svelte";
  import { Loader2Icon } from "lucide-svelte";

  export let featureValues: FeaturesValues;
  export let selectedItem: DatasetItem;
  export let models: string[] = [];
  export let handleSaveItem: (item: DatasetItemSave) => Promise<void>;
  export let isLoading: boolean;
  export let canSaveCurrentItem: boolean;
  export let shouldSaveCurrentItem: boolean;
  export let headerHeight: number = 0;

  let isSaving: boolean = false;

  let embeddings: Embeddings = {};

  $: itemObjects.update(
    (oldObjects) =>
      selectedItem?.objects?.map((object) => {
        const oldObject = oldObjects.find((o) => o.id === object.id);
        if (oldObject) {
          return { ...oldObject, ...object } as ItemObject;
        }
        return object;
      }) || ([] as ItemObject[]),
  );

  $: itemMetas.set({
    mainFeatures: selectedItem.features,
    objectFeatures: Object.values(selectedItem.objects || {})[0]?.features,
    featuresList: featureValues || { main: {}, objects: {} },
    views: selectedItem.views,
    id: selectedItem.id,
    type: selectedItem.type,
  });

  canSave.subscribe((value) => (canSaveCurrentItem = value));

  $: {
    if (selectedItem) {
      newShape.update((old) => ({ ...old, status: "none" }));
      canSave.set(false);
    }
  }

  //$: console.log("Change in SaveData", $saveData);

  const onSave = async () => {
    isSaving = true;
    const savedItem: DatasetItemSave = {
      id: selectedItem.id,
      split: selectedItem.split,
      save_data: $saveData,
      item_features: $itemMetas.mainFeatures,
    };
    await handleSaveItem(savedItem);
    saveData.set([]);
    canSave.set(false);
    isSaving = false;
  };

  $: {
    if (shouldSaveCurrentItem) {
      onSave().catch((err) => console.error(err));
    }
  }
</script>

<div class="w-full h-full grid grid-cols-[48px_calc(100%-380px-48px)_380px]">
  {#if isSaving}
    <div
      class="h-full w-full flex justify-center items-center absolute top-0 left-0 bg-slate-300 z-50 opacity-30"
    >
      <Loader2Icon class="animate-spin" />
    </div>
  {/if}
  <Toolbar />
  <DatasetItemViewer {selectedItem} {embeddings} {isLoading} {headerHeight} />
  <Inspector on:click={onSave} {isLoading} />
  <LoadModelModal
    {models}
    currentDatasetId={selectedItem.datasetId}
    selectedItemId={selectedItem.id}
    bind:embeddings
  />
</div>
