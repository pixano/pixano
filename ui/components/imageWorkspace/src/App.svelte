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

  import * as ort from "onnxruntime-web";
  import type {
    DatasetItem,
    BBox,
    Mask,
    SelectionTool,
    DatasetInfo,
    ItemObject,
  } from "@pixano/core";
  import { SAM } from "@pixano/models";

  import Toolbar from "./components/Toolbar.svelte";
  import ImageCanvas from "./components/ImageCanvas.svelte";
  import ActionsTabs from "./components/ActionsTabs/ActionsTabs.svelte";
  import { loadEmbeddings } from "./lib/api/modelsApi";
  import {
    itemObjects,
    itemBboxes,
    itemMasks,
    interactiveSegmenterModel,
    itemMetas,
    newShape,
    canSave,
  } from "./lib/stores/imageWorkspaceStores";
  import "./index.css";

  export let selectedDataset: DatasetInfo;
  export let selectedItem: DatasetItem;
  export let models: string[] = [];
  export let handleSaveItem: (item: DatasetItem) => void;
  export let isLoading: boolean;

  let selectedTool: SelectionTool;
  let allBBoxes: BBox[] = [];
  let allMasks: Mask[] = [];
  let selectedModelName: string;
  let embeddings: Record<string, ort.Tensor> = {};

  let embeddingAreLoaded: boolean = false;

  $: itemBboxes.subscribe((boxes) => (allBBoxes = boxes));
  $: itemMasks.subscribe((masks) => (allMasks = masks));

  $: itemObjects.set(Object.values(selectedItem.objects || {}).flat());
  $: itemMetas.set({
    features: selectedItem.features,
    views: selectedItem.views,
    id: selectedItem.id,
  });

  $: {
    if (selectedItem) {
      embeddingAreLoaded = false;
      newShape.set(null);
      canSave.set(false);
    }
  }
  $: {
    if (!embeddingAreLoaded) {
      loadEmbeddings(selectedItem, selectedModelName, selectedDataset)
        .then((results) => (embeddings = results))
        .then(() => (embeddingAreLoaded = true))
        .catch((err) => console.error("cannot load Embeddings", err));
    }
  }

  const sam = new SAM();

  async function loadModel() {
    await sam.init("/data/models/" + selectedModelName);
    interactiveSegmenterModel.set(sam);
  }

  const onSave = () => {
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
    handleSaveItem(savedItem);
    canSave.set(false);
  };

  $: {
    if (models.length > 0) {
      let samModels = models.filter((m) => m.includes("sam"));
      if (samModels.length == 1) {
        selectedModelName = samModels[0];
        loadModel().catch((err) => console.error("cannot load model", err));
      }
    }
  }

  $: console.log({ embeddings });
</script>

<div class="w-full h-full grid grid-cols-[48px_calc(100%-380px-48px)_380px]">
  <Toolbar bind:selectedTool />
  <ImageCanvas
    {selectedTool}
    {selectedItem}
    bind:bboxes={allBBoxes}
    bind:masks={allMasks}
    {embeddings}
    {isLoading}
  />
  <ActionsTabs on:click={onSave} {isLoading} />
</div>
