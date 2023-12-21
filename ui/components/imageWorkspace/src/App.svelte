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

  import { onMount } from "svelte";
  import * as ort from "onnxruntime-web";
  import { api } from "@pixano/core";
  import type {
    DatasetItem,
    BBox,
    Mask,
    SelectionTool,
    DatasetInfo,
    ItemObject,
  } from "@pixano/core";
  import { SAM, npy } from "@pixano/models";

  import Toolbar from "./components/Toolbar.svelte";
  import ImageCanvas from "./components/ImageCanvas.svelte";
  import ActionsTabs from "./components/ActionsTabs/ActionsTabs.svelte";
  import {
    itemObjects,
    itemBboxes,
    itemMasks,
    interactiveSegmenterModel,
    itemMetas,
  } from "./lib/stores/imageWorkspaceStores";
  import "./index.css";

  export let selectedDataset: DatasetInfo;
  export let selectedItem: DatasetItem;
  export let models: string[] = [];
  export let handleSaveItem: (item: DatasetItem) => void;

  let selectedTool: SelectionTool;
  let allBBoxes: BBox[] = [];
  let allMasks: Mask[] = [];
  let selectedModelName: string;
  let embeddings: Record<string, ort.Tensor> = {};

  $: itemBboxes.subscribe((boxes) => (allBBoxes = boxes));
  $: itemMasks.subscribe((masks) => (allMasks = masks));

  $: itemObjects.set(Object.values(selectedItem.objects || {}).flat());
  $: itemMetas.set({
    features: selectedItem.features,
    views: selectedItem.views,
    id: selectedItem.id,
  });

  $: loadEmbeddings(selectedItem, selectedModelName)  
    //TODO? .then(()=>{/*<activate model tools>*/}})  *AND/OR* .catch(()=>{/*deactivate model tools*/});

  const sam = new SAM();

  async function loadModel() {
    await sam.init("/data/models/" + selectedModelName);
    interactiveSegmenterModel.set(sam);
  }

  async function loadEmbeddings(selectedItem: DatasetItem, selectedModelName: string) {
    if (selectedModelName != undefined && selectedModelName != "") {
      console.log("Load Embeddings", selectedItem.id, selectedModelName);
      const item = await api.getItemEmbeddings(
        selectedDataset.id,
        selectedItem.id,
        selectedModelName,
      );
      if (item) {
        for (const [viewId, viewEmbeddingBytes] of Object.entries(item.embeddings)) {
          try {
            const viewEmbeddingArray = npy.parse(npy.b64ToBuffer(viewEmbeddingBytes.data));
            embeddings[viewId] = new ort.Tensor(
              "float32",
              viewEmbeddingArray.data,
              viewEmbeddingArray.shape,
            );
          } catch (e) {
            console.warn("AnnotationWorkspace.loadModel - Error loading embeddings", e);
          }
        }
      }
    }
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
  };

  onMount(async () => {
    if (models.length > 0) {
      let samModels = models.filter((m) => m.includes("sam"));
      if (samModels.length == 1) {
        selectedModelName = samModels[0];
        await loadModel();
      }
    }
  });

  $: console.log({ selectedItem });
</script>

<div class="flex w-full h-full">
  <Toolbar bind:selectedTool />
  <ImageCanvas
    {selectedTool}
    {selectedItem}
    bind:bboxes={allBBoxes}
    bind:masks={allMasks}
    {embeddings}
  />
  <ActionsTabs on:click={onSave} />
</div>
