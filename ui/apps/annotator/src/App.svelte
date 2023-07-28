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

  import AnnotationWorkspace from "./lib/AnnotationWorkspace.svelte";
  import { interactiveSegmenterModel } from "./stores";

  import type { BBox, Dataset, ItemData, ItemLabels, Mask } from "@pixano/core";

  // Dataset navigation
  let datasets = null;
  let selectedDataset = null;
  let currentPage = 1;

  let selectedItem: ItemData;
  let annotations: ItemLabels = {};
  let classes = [];
  let masks: Array<Mask> = [];
  let bboxes: Array<BBox> = [];
  let embeddings = {};

  let saveFlag: boolean = false;
  let unselectItemModal = false;

  const defaultModelName = "sam_vit_h_4b8939.onnx";
  let inputModelName: string;
  let modelPromptModal = false;
  let modelNotFoundModal = false;

  let sam = new SAM();

  function until(conditionFunction) {
    const poll = (resolve) => {
      if (conditionFunction()) resolve();
      else setTimeout((_) => poll(resolve), 400);
    };
    return new Promise(poll);
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
    await handleUnselectItem();
    console.log("App.handleUnselectDataset");
    if (!saveFlag) {
      selectedDataset = null;
      currentPage = 1;
    }
  }

  async function handleSelectItem(itemId: string) {
    annotations = {};
    classes = [];
    masks = [];
    bboxes = [];
    embeddings = {};
    // Add temp variables to prevent updating before everything is loaded
    // Otherwise some bounding boxes are displayed incorrectly
    let newAnnotations: ItemLabels = {};
    let newClasses = [];
    let newMasks: Array<Mask> = [];
    let newBboxes: Array<BBox> = [];
    let newEmbeddings = {};

    const start = Date.now();
    selectedItem = await api.getItemDetails(selectedDataset.id, itemId);
    console.log(
      "App.handleSelectItem - api.getItemDetails in",
      Date.now() - start,
      "ms"
    );
    for (const [sourceId, sourceObjects] of Object.entries(
      selectedItem.objects
    )) {
      // Initialize annotations
      newAnnotations[sourceId] = {
        id: sourceId,
        views: {},
        numLabels: 0,
        opened: Object.entries(selectedItem.objects).length > 1 ? false : true,
        visible: true,
      };

      for (const [viewId, viewObjects] of Object.entries(sourceObjects)) {
        // Initialize annotations
        newAnnotations[sourceId].views[viewId] = {
          id: viewId,
          categories: {},
          numLabels: 0,
          opened: Object.entries(sourceObjects).length > 1 ? false : true,
          visible: true,
        };

        // Initalize classes
        newClasses = selectedDataset.categories;

        for (let obj of viewObjects) {
          const catId = obj.category.id;
          const catName = obj.category.name;

          // Masks and bounding boxes
          if (obj.mask || obj.bbox) {
            // Add class if new
            if (!newClasses.some((cls) => cls.id === catId)) {
              newClasses.push({
                id: catId,
                name: catName,
              });
            }

            // Add category if new
            if (!newAnnotations[sourceId].views[viewId].categories[catName]) {
              newAnnotations[sourceId].views[viewId].categories[catName] = {
                labels: {},
                id: catId,
                name: catName,
                opened: false,
                visible: true,
              };
            }

            // Add label
            newAnnotations[sourceId].views[viewId].categories[catName].labels[
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
            newAnnotations[sourceId].numLabels += 1;
            newAnnotations[sourceId].views[viewId].numLabels += 1;

            if (obj.mask) {
              const rle = obj.mask["counts"];
              const size = obj.mask["size"];
              const maskPoly = mask_utils.generatePolygonSegments(rle, size[0]);
              const masksSVG = mask_utils.convertSegmentsToSVG(maskPoly);

              // Add mask
              newMasks.push({
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
              newBboxes.push({
                id: obj.id,
                viewId: viewId,
                bbox: [obj.bbox.x, obj.bbox.y, obj.bbox.width, obj.bbox.height], //still normalized
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

    annotations = newAnnotations;
    classes = newClasses;
    masks = newMasks;
    bboxes = newBboxes;

    // Embeddings
    for (let view of selectedItem.views) {
      let viewEmbedding = null;
      const start = Date.now();
      const viewEmbeddingArrayBytes = await api.getViewEmbedding(
        selectedDataset.id,
        selectedItem.id,
        view.id
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
      newEmbeddings[view.id] = viewEmbedding;
    }

    embeddings = newEmbeddings;
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
    let anns = [];

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
              let ann = {
                id: label.id,
                mask: mask ? mask.rle : null,
                mask_source: label.sourceId,
                bbox: bbox ? bbox.bbox : null,
                bbox_source: label.sourceId,
                view_id: label.viewId,
                category_id: label.categoryId,
                category_name: label.categoryName,
              };
              anns.push(ann);
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
  }

  async function handleLoadNextPage() {
    console.log("App.handleLoadNextPage");
    currentPage = currentPage + 1;

    const start = Date.now();
    let new_dbImages = await api.getDatasetItems(
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
    const start = Date.now();
    datasets = await api.getDatasetsList();
    console.log(
      "App.onMount - api.getDatasetsList in",
      Date.now() - start,
      "ms"
    );

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
  class="pt-20 h-screen w-screen text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300"
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
