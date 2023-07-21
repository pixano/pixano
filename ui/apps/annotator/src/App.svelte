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
    ConfirmModal,
    Header,
    Library,
    LoadingLibrary,
    PromptModal,
    WarningModal,
  } from "@pixano/core";
  import { mask_utils, npy, SAM } from "@pixano/models";

  import AnnotationWorkspace from "./lib/AnnotationWorkspace.svelte";
  import * as api from "./lib/api";
  import { interactiveSegmenterModel } from "./stores";

  import type {
    ItemData,
    Mask,
    AnnotationCategory,
    AnnotationLabel,
    ViewData,
    DatasetItems,
  } from "@pixano/canvas2d/src/interfaces";

  // Dataset navigation
  let datasets = null;
  let selectedDataset = null;
  let currentPage = 1;

  let selectedItem: ItemData;
  let embeddings = {};

  let saveFlag: boolean = false;
  let unselectItemConfirm = false;

  let masks: Array<Mask> = [];
  let annotations: Array<AnnotationCategory> = [];
  let classes = [];
  let itemDetails = null;
  let datasetItems: DatasetItems = null;

  let modelPrompt = false;
  let modelNotFoundWarning = false;
  let modelInput: string;

  let sam = new SAM();

  function until(conditionFunction) {
    const poll = (resolve) => {
      if (conditionFunction()) resolve();
      else setTimeout((_) => poll(resolve), 400);
    };
    return new Promise(poll);
  }

  async function handleSelectDataset(event: CustomEvent) {
    selectedDataset = event.detail.dataset;

    datasetItems = await api.getDatasetItems(selectedDataset.id, currentPage);
    //select first item
    let firstItem = datasetItems.items[0];
    for (let feat of firstItem) {
      if (feat.name === "id") {
        handleSelectItem({ id: feat.value });
        break;
      }
    }
  }

  function handleUnselectDataset() {
    selectedDataset = null;
    selectedItem = null;
  }

  async function handleSelectItem(data) {
    //selected item
    console.log("=== LOADING SELECTED ITEM ===");
    const start = Date.now();
    itemDetails = await api.getItemDetails(selectedDataset.id, data.id);
    console.log("getItemDetails time (ms):", Date.now() - start);
    let views: Array<ViewData> = [];
    for (let viewId of Object.keys(itemDetails.views)) {
      let view: ViewData = {
        viewId: viewId,
        imageURL: itemDetails.views[viewId].image,
      };
      views.push(view);
    }
    selectedItem = {
      dbName: selectedDataset.name,
      id: data.id,
      views: views,
    };
    console.log("item loaded:", selectedItem);

    //build annotations, masks and classes
    masks = [];
    annotations = [];

    //predefined classes from spec.json "categories"
    classes = selectedDataset.categories;

    let struct_views_categories = {};
    for (let viewId of Object.keys(itemDetails.views)) {
      let struct_categories: { [key: string]: AnnotationCategory } = {};

      for (let i = 0; i < itemDetails.views[viewId].objects.id.length; ++i) {
        const mask_rle = itemDetails.views[viewId].objects.segmentation[i];
        const cat_name = itemDetails.views[viewId].objects.category[i].name;

        if (mask_rle) {
          //separate in case we add bboxes or other annotation types later
          // ensure all items goes in unique category (by name)
          if (!struct_categories[cat_name]) {
            let annotation: AnnotationCategory = {
              id: itemDetails.views[viewId].objects.category[i].id,
              name: cat_name,
              viewId: viewId,
              labels: [],
              visible: true,
            };
            struct_categories[cat_name] = annotation;
          }
        }

        if (mask_rle) {
          const rle = mask_rle["counts"];
          const size = mask_rle["size"];
          const maskPolygons = mask_utils.generatePolygonSegments(rle, size[0]);
          const masksSVG = mask_utils.convertSegmentsToSVG(maskPolygons);

          masks.push({
            viewId: viewId,
            id: itemDetails.views[viewId].objects.id[i],
            mask: masksSVG,
            rle: mask_rle,
            catId: itemDetails.views[viewId].objects.category[i].id,
            opacity: 1.0,
            visible: true,
          });
          let label: AnnotationLabel = {
            id: itemDetails.views[viewId].objects.id[i],
            viewId: viewId,
            type: "mask",
            opacity: 1.0,
            visible: true,
          };
          struct_categories[cat_name].labels.push(label);
        }
      }
      struct_views_categories[viewId] = struct_categories;
    }
    for (let view in struct_views_categories) {
      for (let cat_name in struct_views_categories[view]) {
        annotations.push(struct_views_categories[view][cat_name]);
      }
    }

    console.log("init masks", masks);
    //unique classes from existing annotations
    for (let category of annotations) {
      if (!classes.some((cls) => cls.id === category.id)) {
        classes.push({
          id: category.id,
          name: category.name,
        });
      }
    }

    // Embeddings
    console.log("=== LOADING EMBEDDING ===");
    for (let viewId of Object.keys(itemDetails.views)) {
      const viewEmbeddingArrayBytes = await api.getViewEmbedding(
        selectedDataset.id,
        itemDetails.id,
        viewId
      );
      let viewEmbedding = null;
      try {
        const viewEmbeddingArray = npy.parse(viewEmbeddingArrayBytes);
        viewEmbedding = new ort.Tensor(
          "float32",
          viewEmbeddingArray.data,
          viewEmbeddingArray.shape
        );
      } catch (err) {
        console.log("Embedding not loaded", err);
      }
      embeddings[viewId] = viewEmbedding;
    }
    console.log("Embedding:", embeddings);
    console.log("DONE");
  }

  function toggleUnselectItemModal() {
    unselectItemConfirm = !unselectItemConfirm;
  }

  function confirmUnselectItem() {
    saveFlag = false;
    toggleUnselectItemModal();
  }

  async function handleUnselectItem() {
    if (!saveFlag) {
      unselectItem();
    } else {
      toggleUnselectItemModal();
      await until((_) => unselectItemConfirm == false);
      if (!saveFlag) {
        unselectItem();
      }
    }
  }

  function unselectItem() {
    unselectItemConfirm = false;
    selectedDataset = null;
    selectedItem = null;
    embeddings = {};
    masks = [];
    annotations = [];
    classes = [];
    currentPage = 1;
  }

  function saveAnns(annotations, masks) {
    console.log("App - save annotations");
    //format annotation data for export
    let anns = [];
    for (let mask of masks) {
      const mask_class = annotations.find(
        (obj) => obj.category_id === mask.catId && obj.viewId === mask.viewId
      );
      let ann = {
        id: mask.id,
        view_id: mask.viewId,
        category_id: mask_class.category_id,
        category_name: mask_class.category_name,
        mask: mask.rle,
        mask_source: "Pixano Annotator",
      };
      anns.push(ann);
    }
    api.postAnnotations(anns, selectedDataset.id, selectedItem.id);
  }

  async function handleLoadNextPage() {
    currentPage = currentPage + 1;
    let new_dbImages = await api.getDatasetItems(
      selectedDataset.id,
      currentPage
    );
    if (new_dbImages) {
      datasetItems.items = datasetItems.items.concat(new_dbImages.items);
    } else {
      //end of dataset : reset last page
      currentPage = currentPage - 1;
    }
  }

  async function toggleModelPromptModal() {
    modelPrompt = false;
    // Try loading model name from user input
    try {
      await sam.init("/models/" + modelInput);
      interactiveSegmenterModel.set(sam);
    } catch (e) {
      toggleModelNotFoundModal();
    }
  }

  function toggleModelNotFoundModal() {
    modelNotFoundWarning = !modelNotFoundWarning;
  }

  function handleSaveAnns() {
    saveAnns(annotations, masks);
    saveFlag = false;
  }

  function handleEnableSaveFlag() {
    saveFlag = true;
  }

  onMount(async () => {
    datasets = await api.getDatasetsList();

    let modelName = "sam_vit_h_4b8939.onnx";

    // Try loading default model name
    try {
      await sam.init("/models/" + modelName);
      interactiveSegmenterModel.set(sam);
    } catch (e) {
      // If default not found, ask user for model name
      modelPrompt = true;
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
        {selectedItem}
        {embeddings}
        bind:annotations
        bind:masks
        {classes}
        {datasetItems}
        {currentPage}
        bind:saveFlag
        on:selectItem={(event) => handleSelectItem(event.detail)}
        on:loadNextPage={handleLoadNextPage}
        on:enableSaveFlag={handleEnableSaveFlag}
      />
    {:else}
      <Library
        {datasets}
        buttonLabel="Annotate"
        on:selectDataset={handleSelectDataset}
      />
    {/if}
  {:else}
    <LoadingLibrary />
  {/if}
  {#if modelPrompt}
    <PromptModal
      message="Please provide the name of your ONNX model for interactive segmentation."
      placeholder="sam_vit_h_4b8939.onnx"
      bind:input={modelInput}
      on:confirm={toggleModelPromptModal}
    />
  {/if}
  {#if modelNotFoundWarning}
    <WarningModal
      message="models/{modelInput} was not found in your dataset library."
      details="Please refer to our interactive annotation notebook for information on how to export your model to ONNX."
      moreDetails="Please also check your internet connection, as it is currently required to initialize an ONNX model."
      on:confirm={toggleModelNotFoundModal}
    />
  {/if}
  {#if unselectItemConfirm}
    <ConfirmModal
      message="You have unsaved changes."
      confirm="Close without saving"
      on:confirm={confirmUnselectItem}
      on:cancel={toggleUnselectItemModal}
    />
  {/if}
</div>
