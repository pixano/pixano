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
  import type { DatasetItem, BBox, Mask, SelectionTool, DatasetInfo } from "@pixano/core";
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
  } from "./lib/stores/stores";
  import "./index.css";

  export let selectedDataset: DatasetInfo;
  export let selectedItem: DatasetItem;
  export let models: string[] = [];

  let selectedTool: SelectionTool;
  let allBBoxes: BBox[] = [];
  let allMasks: Mask[] = [];
  let selectedModelName: string;
  let embeddings: Record<string, ort.Tensor> = {};

  $: itemBboxes.subscribe((boxes) => (allBBoxes = boxes));
  $: itemMasks.subscribe((masks) => (allMasks = masks));
  $: console.log({ selectedDataset, selectedItem, allBBoxes });

  $: itemObjects.set(Object.values(selectedItem.objects || {}).flat());
  $: itemMetas.set({
    features: selectedItem.features,
    views: selectedItem.views,
    id: selectedItem.id,
  });

  const sam = new SAM();

  async function loadModel() {
    await sam.init("/data/models/" + selectedModelName);
    interactiveSegmenterModel.set(sam);

    // Embeddings

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
    } else {
      selectedModelName = "";
    }
  }

  onMount(async () => {
    if (models.length > 0) {
      let samModels = models.filter((m) => m.includes("sam"));
      if (samModels.length == 1) {
        selectedModelName = samModels[0];
        await loadModel();
      }
    }
  });
</script>

<div class="flex w-full pt-[81px] h-full">
  <Toolbar bind:selectedTool />
  <ImageCanvas
    {selectedTool}
    {selectedItem}
    bind:bboxes={allBBoxes}
    bind:masks={allMasks}
    {embeddings}
  />
  <ActionsTabs />
</div>
