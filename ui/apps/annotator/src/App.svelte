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

  import type {
    Dataset,
    ItemData,
    Mask,
    AnnotationCategory,
    AnnotationLabel,
  } from "@pixano/core";

  // Dataset navigation
  let datasets = null;
  let selectedDataset = null;
  let currentPage = 1;

  let selectedItem: ItemData;
  let embeddings = {};

  let saveFlag: boolean = false;
  let unselectItemModal = false;

  let masks: Array<Mask> = [];
  let annotations: Array<AnnotationCategory> = [];
  let classes = [];

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

  async function handleSelectItem(id: string) {
    console.log("App.handleSelectItem");
    const start = Date.now();
    selectedItem = await api.getItemDetails(selectedDataset.id, id);
    console.log(
      "App.handleSelectItem - api.getItemDetails in",
      Date.now() - start,
      "ms"
    );

    //build annotations, masks and classes
    masks = [];
    annotations = [];
    classes = selectedDataset.categories;
    let struct_views_categories = {};
    for (let view of selectedItem.views) {
      let struct_categories: { [key: string]: AnnotationCategory } = {};
      for (let i = 0; i < selectedItem.objects[view.id].id.length; ++i) {
        const maskRLE = selectedItem.objects[view.id].masks[i];
        const catName = selectedItem.objects[view.id].categories[i].name;

        if (maskRLE) {
          //separate in case we add bboxes or other annotation types later
          // ensure all items goes in unique category (by name)
          if (!struct_categories[catName]) {
            let annotation: AnnotationCategory = {
              id: selectedItem.objects[view.id].categories[i].id,
              name: catName,
              viewId: view.id,
              labels: [],
              visible: true,
            };
            struct_categories[catName] = annotation;
          }
        }

        if (maskRLE) {
          const rle = maskRLE["counts"];
          const size = maskRLE["size"];
          const maskPolygons = mask_utils.generatePolygonSegments(rle, size[0]);
          const masksSVG = mask_utils.convertSegmentsToSVG(maskPolygons);

          masks.push({
            viewId: view.id,
            id: selectedItem.objects[view.id].id[i],
            mask: masksSVG,
            rle: maskRLE,
            catId: selectedItem.objects[view.id].categories[i].id,
            opacity: 1.0,
            visible: true,
          });
          let label: AnnotationLabel = {
            id: selectedItem.objects[view.id].id[i],
            viewId: view.id,
            type: "mask",
            opacity: 1.0,
            visible: true,
          };
          struct_categories[catName].labels.push(label);
        }
      }
      struct_views_categories[view.id] = struct_categories;
    }
    for (let view in struct_views_categories) {
      for (let cat_name in struct_views_categories[view]) {
        annotations.push(struct_views_categories[view][cat_name]);
      }
    }

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
      embeddings[view.id] = viewEmbedding;
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
    selectedDataset = null;
    selectedItem = null;
    embeddings = {};
    masks = [];
    annotations = [];
    classes = [];
    currentPage = 1;
  }

  function handleSaveAnns() {
    console.log("App.handleSaveAnns");
    saveFlag = false;
    let anns = [];

    for (let mask of masks) {
      const maskCategory = annotations.find(
        (cat) => cat.id === mask.catId && cat.viewId === mask.viewId
      );
      let ann = {
        id: mask.id,
        view_id: mask.viewId,
        category_id: maskCategory.id,
        category_name: maskCategory.name,
        mask: mask.rle,
        mask_source: "Pixano Annotator",
      };
      anns.push(ann);
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
        {embeddings}
        bind:annotations
        bind:masks
        {classes}
        {currentPage}
        bind:saveFlag
        on:selectItem={(event) => handleSelectItem(event.detail.id)}
        on:loadNextPage={handleLoadNextPage}
        on:enableSaveFlag={() => (saveFlag = true)}
      />
    {:else}
      <Library
        {datasets}
        buttonLabel="Annotate"
        on:selectDataset={(event) => handleSelectDataset(event.detail.dataset)}
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
