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

  // Imports
  import * as ort from "onnxruntime-web";
  import { onMount } from "svelte";

  import {
    api,
    ConfirmModal,
    Header,
    Library,
    LoadingLibrary,
    PromptModal,
    WarningModal,
  } from "@pixano/core";
  import { mask_utils, npy, SAM } from "@pixano/models";

  import AnnotationWorkspace from "./AnnotationWorkspace.svelte";
  import { interactiveSegmenterModel } from "./stores";

  import type {
    BBox,
    CategoryData,
    Dataset,
    ItemData,
    ItemLabels,
    ItemObjects,
    Mask,
  } from "@pixano/core";

  // Dataset navigation
  let datasets: Array<Dataset>;
  let selectedDataset: Dataset;
  let currentPage = 1;

  let selectedItem: ItemData;
  let annotations: ItemLabels;
  let classes: Array<CategoryData>;
  let masks: Array<Mask>;
  let bboxes: Array<BBox>;
  let embeddings = {};

  let saveFlag = false;
  let unselectItemModal = false;

  const defaultModelName = "sam_vit_h_4b8939.onnx";
  let inputModelName: string;
  let modelPromptModal = false;
  let modelNotFoundModal = false;

  const sam = new SAM();

  function until(conditionFunction: Function): Promise<Function> {
    const poll = (resolve) => {
      if (conditionFunction()) resolve();
      else setTimeout((_) => poll(resolve), 400);
    };
    return new Promise(poll);
  }

  async function handleGetDatasets() {
    console.log("App.handleGetDatasets");
    const start = Date.now();
    datasets = await api.getDatasetsList();
    console.log(
      "App.handleGetDatasets - api.getDatasetsList in",
      Date.now() - start,
      "ms"
    );
  }

  async function handleSelectDataset(dataset: Dataset) {
    console.log("App.handleSelectDataset");
    selectedDataset = dataset;
    const start = Date.now();
    selectedDataset.page = await api.getDatasetItems(
      selectedDataset.id,
      currentPage
    );
    console.log(
      "App.handleSelectDataset - api.getDatasetItems in",
      Date.now() - start,
      "ms"
    );

    // Select first item
    const firstItemId = selectedDataset.page.items[0].find((feature) => {
      return feature.name === "id";
    }).value;
    handleSelectItem(firstItemId);
  }

  async function handleUnselectDataset() {
    console.log("App.handleUnselectDataset");
    await handleUnselectItem();
    if (!saveFlag) {
      selectedDataset = null;
      currentPage = 1;
      handleGetDatasets();
    }
  }

  async function handleSelectItem(itemId: string) {
    annotations = {};
    classes = [];
    masks = [];
    bboxes = [];
    embeddings = {};

    const start = Date.now();
    const itemDetails = await api.getItemDetails(selectedDataset.id, itemId);
    selectedItem = itemDetails["itemData"] as ItemData;
    const ItemObjects = itemDetails["itemObjects"] as ItemObjects;

    console.log(
      "App.handleSelectItem - api.getItemDetails in",
      Date.now() - start,
      "ms"
    );

    for (const [sourceId, sourceObjects] of Object.entries(ItemObjects)) {
      // Initialize annotations
      annotations[sourceId] = {
        id: sourceId,
        views: {},
        numLabels: 0,
        opened: Object.entries(ItemObjects).length > 1 ? false : true,
        visible: true,
      };

      for (const [viewId, viewObjects] of Object.entries(sourceObjects)) {
        // Initialize annotations
        annotations[sourceId].views[viewId] = {
          id: viewId,
          categories: {},
          numLabels: 0,
          opened: Object.entries(sourceObjects).length > 1 ? false : true,
          visible: true,
        };

        for (const obj of viewObjects) {
          const catId = obj.category.id;
          const catName = obj.category.name;

          // Masks and bounding boxes
          if (obj.mask || obj.bbox) {
            // Add class if new
            if (!classes.some((cls) => cls.id === catId)) {
              classes.push({
                id: catId,
                name: catName,
              });
            }

            // Add category if new
            if (!annotations[sourceId].views[viewId].categories[catId]) {
              annotations[sourceId].views[viewId].categories[catId] = {
                labels: {},
                id: catId,
                name: catName,
                opened: false,
                visible: true,
              };
            }

            // Add label
            annotations[sourceId].views[viewId].categories[catId].labels[
              obj.id
            ] = {
              id: obj.id,
              categoryId: catId,
              categoryName: catName,
              sourceId: sourceId,
              viewId: viewId,
              confidence:
                obj.bbox && obj.bbox.predicted ? obj.bbox.confidence : null,
              bboxOpacity: 1.0,
              maskOpacity: 1.0,
              visible: true,
            };

            // Update counters
            annotations[sourceId].numLabels += 1;
            annotations[sourceId].views[viewId].numLabels += 1;

            if (obj.mask) {
              const rle = obj.mask["counts"];
              const size = obj.mask["size"];
              const maskPoly = mask_utils.generatePolygonSegments(rle, size[0]);
              const masksSVG = mask_utils.convertSegmentsToSVG(maskPoly);

              // Add mask
              masks.push({
                id: obj.id,
                viewId: viewId,
                svg: masksSVG,
                rle: obj.mask,
                catId: catId,
                visible: true,
                opacity: 1.0,
              });
            }

            if (obj.bbox) {
              // Add bbox
              bboxes.push({
                id: obj.id,
                viewId: viewId,
                bbox: [
                  obj.bbox.x * selectedItem.views[viewId].width,
                  obj.bbox.y * selectedItem.views[viewId].height,
                  obj.bbox.width * selectedItem.views[viewId].width,
                  obj.bbox.height * selectedItem.views[viewId].height,
                ], // denormalized
                tooltip:
                  catName +
                  (obj.bbox.predicted
                    ? " " + obj.bbox.confidence.toFixed(2)
                    : ""),
                catId: catId,
                visible: true,
                opacity: 1.0,
              });
            }
          } else {
            console.log(
              "App.handleSelectItem - Warning: no mask nor bounding box for item",
              obj.id
            );
            continue;
          }
        }
      }
    }

    // Embeddings
    for (const viewId of Object.keys(selectedItem.views)) {
      let viewEmbedding = null;
      const start = Date.now();
      const viewEmbeddingArrayBytes = await api.getViewEmbedding(
        selectedDataset.id,
        selectedItem.id,
        viewId
      );
      console.log(
        "App.handleSelectItem - api.getViewEmbedding in",
        Date.now() - start,
        "ms"
      );

      if (viewEmbeddingArrayBytes) {
        try {
          const viewEmbeddingArray = npy.parse(viewEmbeddingArrayBytes);
          viewEmbedding = new ort.Tensor(
            "float32",
            viewEmbeddingArray.data,
            viewEmbeddingArray.shape
          );
        } catch (e) {
          console.log("App.handleSelectItem - Error loading embeddings", e);
        }
      }
      embeddings[viewId] = viewEmbedding;
    }
  }

  async function handleUnselectItem() {
    console.log("App.handleUnselectItem");
    if (!saveFlag) {
      unselectItem();
    } else {
      unselectItemModal = true;
      await until((_) => unselectItemModal == false);
      if (!saveFlag) {
        unselectItem();
      }
    }
  }

  function unselectItem() {
    unselectItemModal = false;
    selectedItem = null;
    annotations = {};
    classes = [];
    masks = [];
    bboxes = [];
    embeddings = {};
  }

  function handleSaveAnns() {
    console.log("App.handleSaveAnns");
    saveFlag = false;
    const anns = [];

    for (const sourceLabels of Object.values(annotations)) {
      if (
        sourceLabels.id === "Ground truth" ||
        sourceLabels.id === "Pixano Annotator"
      ) {
        for (const viewLabels of Object.values(sourceLabels.views)) {
          for (const catLabels of Object.values(viewLabels.categories)) {
            for (const label of Object.values(catLabels.labels)) {
              const mask = masks.find(
                (m) => m.id === label.id && m.viewId === label.viewId
              );
              const bbox = bboxes.find(
                (b) => b.id === label.id && b.viewId === label.viewId
              );
              anns.push({
                id: label.id,
                mask: {
                  size: mask.rle ? mask.rle.size : [0, 0],
                  counts: mask.rle ? mask.rle.counts : [],
                },
                mask_source: label.sourceId,
                bbox: {
                  coords: bbox ? bbox.bbox : [0, 0, 0, 0],
                  format: "xywh",
                },
                bbox_source: label.sourceId,
                view_id: label.viewId,
                category_id: label.categoryId,
                category_name: label.categoryName,
              });
            }
          }
        }
      }
    }

    const start = Date.now();
    api.postAnnotations(anns, selectedDataset.id, selectedItem.id);
    console.log(
      "App.handleSaveAnns - api.postAnnotations in",
      Date.now() - start,
      "ms"
    );

    // Reload annotations
    handleSelectItem(selectedItem.id);
  }

  async function handleLoadNextPage() {
    console.log("App.handleLoadNextPage");
    currentPage = currentPage + 1;

    const start = Date.now();
    const new_dbImages = await api.getDatasetItems(
      selectedDataset.id,
      currentPage
    );
    console.log(
      "App.handleLoadNextPage - api.getDatasetItems in",
      Date.now() - start,
      "ms"
    );

    if (new_dbImages) {
      selectedDataset.page.items = selectedDataset.page.items.concat(
        new_dbImages.items
      );
    } else {
      // End of dataset: reset last page
      currentPage = currentPage - 1;
    }
  }

  async function handleModelPrompt() {
    modelPromptModal = false;
    // Try loading model name from user input
    try {
      await sam.init("/models/" + inputModelName);
      interactiveSegmenterModel.set(sam);
    } catch (e) {
      modelNotFoundModal = false;
    }
  }

  onMount(async () => {
    console.log("App.onMount");
    handleGetDatasets();
    // Try loading default model
    try {
      await sam.init("/models/" + defaultModelName);
      interactiveSegmenterModel.set(sam);
    } catch (e) {
      // If default not found, ask user for model
      modelPromptModal = true;
    }
  });
</script>

<Header
  app="Annotator"
  bind:selectedDataset
  bind:selectedItem
  {saveFlag}
  on:unselectDataset={handleUnselectDataset}
  on:unselectItem={handleUnselectItem}
  on:saveAnns={handleSaveAnns}
/>
<div
  class="pt-20 h-screen w-full
  bg-white dark:bg-zinc-800
  text-zinc-800 dark:text-zinc-300"
>
  {#if datasets}
    {#if selectedItem}
      <AnnotationWorkspace
        {selectedDataset}
        {selectedItem}
        bind:annotations
        {classes}
        bind:masks
        bind:bboxes
        {embeddings}
        {currentPage}
        bind:saveFlag
        on:selectItem={(event) => handleSelectItem(event.detail)}
        on:loadNextPage={handleLoadNextPage}
        on:enableSaveFlag={() => (saveFlag = true)}
      />
    {:else}
      <Library
        {datasets}
        buttonLabel="Annotate"
        on:selectDataset={(event) => handleSelectDataset(event.detail)}
      />
    {/if}
  {:else}
    <LoadingLibrary />
  {/if}
  {#if modelPromptModal}
    <PromptModal
      message="Please provide the name of your ONNX model for interactive segmentation."
      placeholder={defaultModelName}
      bind:input={inputModelName}
      on:confirm={handleModelPrompt}
    />
  {/if}
  {#if modelNotFoundModal}
    <WarningModal
      message="models/{inputModelName} was not found in your dataset library."
      details="Please refer to our interactive annotation notebook for information on how to export your model to ONNX."
      moreDetails="Please also check your internet connection, as it is currently required to initialize an ONNX model."
      on:confirm={() => (modelNotFoundModal = false)}
    />
  {/if}
  {#if unselectItemModal}
    <ConfirmModal
      message="You have unsaved changes."
      confirm="Close without saving"
      on:confirm={() => ((saveFlag = false), (unselectItemModal = false))}
      on:cancel={() => (unselectItemModal = false)}
    />
  {/if}
</div>
