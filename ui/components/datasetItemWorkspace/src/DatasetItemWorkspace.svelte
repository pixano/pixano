<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

<<<<<<< HEAD
  import type { DatasetItem, FeaturesValues } from "@pixano/core";
=======
  import type { DatasetItem, ItemObject, FeaturesValues } from "@pixano/core";
>>>>>>> f7ef643eb84267348183a58d363cb3df4e6e6425

  import Toolbar from "./components/Toolbar.svelte";
  import Inspector from "./components/Inspector/InspectorInspector.svelte";
  import LoadModelModal from "./components/LoadModelModal.svelte";
  import {
    itemObjects,
    itemMetas,
    newShape,
    canSave,
  } from "./lib/stores/datasetItemWorkspaceStores";
  import "./index.css";
  import type { Embeddings } from "./lib/types/datasetItemWorkspaceTypes";
  import DatasetItemViewer from "./components/DatasetItemViewer/DatasetItemViewer.svelte";
  import { Loader2Icon } from "lucide-svelte";

  export let featureValues: FeaturesValues;
  export let selectedItem: DatasetItem;
  export let models: string[] = [];
  export let handleSaveItem: (item: DatasetItem) => Promise<void>;
  export let isLoading: boolean;
  export let canSaveCurrentItem: boolean;
  export let shouldSaveCurrentItem: boolean;

  let isSaving: boolean = false;
  let brightness: number = 0;
  let contrast: number = 0;

  let embeddings: Embeddings = {};

  $: itemObjects.update((oldObjects) =>
    selectedItem?.objects.map((object) => {
      const oldObject = oldObjects.find((o) => o.id === object.id);
      if (oldObject) {
        return { ...oldObject, ...object };
      }
      return object;
    }),
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

  const onSave = async () => {
    isSaving = true;
    const objects = $itemObjects;
    let savedItem = { ...selectedItem, objects } as DatasetItem;

    itemMetas.subscribe((value) => {
      savedItem.features = value.mainFeatures;
    });
    await handleSaveItem(savedItem);
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
  <DatasetItemViewer {selectedItem} {embeddings} {isLoading} {brightness} {contrast} />
  <Inspector on:click={onSave} {isLoading} bind:brightness bind:contrast />
  <LoadModelModal
    {models}
    currentDatasetId={selectedItem.datasetId}
    selectedItemId={selectedItem.id}
    bind:embeddings
  />
</div>
