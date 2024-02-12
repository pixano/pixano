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

  import type {
    DatasetItem,
    BBox,
    Mask,
    SelectionTool,
    DatasetInfo,
    ItemObject,
  } from "@pixano/core";

  import Toolbar from "./components/Toolbar.svelte";
  import ImageCanvas from "./components/ImageCanvas.svelte";
  import ImageInspector from "./components/ImageInspector/ImageInspector.svelte";
  import LoadModelModal from "./components/LoadModelModal.svelte";
  import {
    itemObjects,
    itemBboxes,
    itemMasks,
    itemMetas,
    itemFeaturesAvailableValues,
    newShape,
    canSave,
  } from "./lib/stores/imageWorkspaceStores";
  import "./index.css";
  import type { Embeddings } from "./lib/types/imageWorkspaceTypes";
  import { Loader2Icon } from "lucide-svelte";
  import { onMount } from "svelte";
  import { api } from "@pixano/core/src";

  export let currentDatasetId: DatasetInfo["id"];
  export let selectedItem: DatasetItem;
  export let models: string[] = [];
  export let handleSaveItem: (item: DatasetItem) => Promise<void>;
  export let isLoading: boolean;
  export let canSaveCurrentItem: boolean;
  export let shouldSaveCurrentItem: boolean;

  let isSaving: boolean = false;

  let selectedTool: SelectionTool;
  let allBBoxes: BBox[] = [];
  let allMasks: Mask[] = [];
  let embeddings: Embeddings = {};

  $: itemBboxes.subscribe((boxes) => (allBBoxes = boxes));
  $: itemMasks.subscribe((masks) => (allMasks = masks));

  $: itemObjects.set(
    Object.values(selectedItem.objects || {})
      .flat()
      .map((obj) => ({ ...obj, displayControl: { hidden: false } })),
  );
  $: itemMetas.set({
    features: selectedItem.features,
    itemFeatures: Object.values(selectedItem.objects || {})[0]?.features,
    views: selectedItem.views,
    id: selectedItem.id,
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
    let savedItem = { ...selectedItem };

    itemObjects.subscribe((value) => {
      savedItem.objects = value.reduce(
        (acc, obj) => {
          acc[obj.id] = obj;
          return acc;
        },
        {} as Record<string, ItemObject>,
      );
    });
    itemMetas.subscribe((value) => {
      savedItem.features = value.features;
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

  onMount(() => {
    api
      .getDataset(currentDatasetId)
      .then((datasetWithFeats) => {
        itemFeaturesAvailableValues.set(
          datasetWithFeats.features_values || { scene: {}, objects: {} }
        );
      })
      .catch((err) => console.error(err));
  });
</script>

<div class="w-full h-full grid grid-cols-[48px_calc(100%-380px-48px)_380px]">
  {#if isSaving}
    <div
      class="h-full w-full flex justify-center items-center absolute top-0 left-0 bg-slate-300 z-50 opacity-30"
    >
      <Loader2Icon class="animate-spin" />
    </div>
  {/if}
  <Toolbar bind:selectedTool />
  <ImageCanvas
    {selectedTool}
    {selectedItem}
    bind:bboxes={allBBoxes}
    bind:masks={allMasks}
    {embeddings}
    {isLoading}
  />
  <ImageInspector on:click={onSave} {isLoading} />
  <LoadModelModal
    {models}
    {currentDatasetId}
    selectedItemId={selectedItem.id}
    bind:embeddings
    {selectedTool}
  />
</div>
