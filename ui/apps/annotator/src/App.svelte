<script lang="ts">
  /**
  @copyright CEA-LIST/DIASI/SIALV/LVA (2023)
  @author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
  @license CECILL-C

  This software is a collaborative computer program whose purpose is to
  generate and explore labeled data for computer vision applications.
  This software is governed by the CeCILL-C license under French law and
  abiding by the rules of distribution of free software. You can use, 
  modify and/ or redistribute the software under the terms of the CeCILL-C
  license as circulated by CEA, CNRS and INRIA at the following URL

  http://www.cecill.info
  */

  // Imports
  import * as ort from "onnxruntime-web";
  import { onMount } from "svelte";

  import ConfirmModal from "../../../components/core/src/ConfirmModal.svelte";
  import Header from "../../../components/core/src/Header.svelte";
  import LoadingLibrary from "../../../components/core/src/LoadingLibrary.svelte";
  import Library from "../../../components/core/src/Library.svelte";
  import PromptModal from "../../../components/core/src/PromptModal.svelte";
  import WarningModal from "../../../components/core/src/WarningModal.svelte";
  import * as npyjs from "../../../components/models/src/npy";
  import { SAM } from "../../../components/models/src/Sam";
  import {
    convertSegmentsToSVG,
    generatePolygonSegments,
  } from "../../../components/models/src/mask_utils";
  import AnnotationWorkspace from "./lib/AnnotationWorkspace.svelte";
  import * as api from "./lib/api";
  import { interactiveSegmenterModel } from "./stores";

  import type {
    ItemData,
    MaskGT,
    AnnotationsLabels,
    AnnLabel,
    ViewData,
    DatabaseFeats,
  } from "../../../components/canvas2d/src/interfaces";

  // Dataset navigation
  let datasets = null;
  let selectedDataset = null;
  let curPage = 1;

  let selectedItem: ItemData;
  let selectedItemEmbeddings = {};

  let saveFlag: boolean = false;
  let unselectItemConfirm = false;

  let masksGT: Array<MaskGT> = [];
  let annotations: Array<AnnotationsLabels> = [];
  let classes = [];
  let itemDetails = null;
  let dbImages: DatabaseFeats = null;

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

  async function selectDataset(event: CustomEvent) {
    selectedDataset = event.detail.dataset;

    dbImages = await api.getDatasetItems(selectedDataset.id, curPage);
    //select first item
    let firstItem = dbImages.items[0];
    for (let feat of firstItem) {
      if (feat.name === "id") {
        selectItem({ id: feat.value });
        break;
      }
    }
  }

  async function selectItem(data) {
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

    //build annotations, masksGT and classes
    masksGT = [];
    annotations = [];

    //predefined classes from spec.json "categories"
    classes = selectedDataset.categories;

    let struct_views_categories = {};
    for (let viewId of Object.keys(itemDetails.views)) {
      let struct_categories = {};

      for (let i = 0; i < itemDetails.views[viewId].objects.id.length; ++i) {
        const mask_rle = itemDetails.views[viewId].objects.segmentation[i];
        const cat_name = itemDetails.views[viewId].objects.category[i].name;

        if (mask_rle) {
          //separate in case we add bboxes or other annotation types later
          // ensure all items goes in unique category (by name)
          if (!struct_categories[cat_name]) {
            let annotation: AnnotationsLabels = {
              viewId: viewId,
              category_name: cat_name,
              category_id: itemDetails.views[viewId].objects.category[i].id,
              items: [],
              visible: true,
            };
            struct_categories[cat_name] = annotation;
          }
        }

        if (mask_rle) {
          const rle = mask_rle["counts"];
          const size = mask_rle["size"];
          const maskPolygons = generatePolygonSegments(rle, size[0]);
          const masksSVG = convertSegmentsToSVG(maskPolygons);

          masksGT.push({
            viewId: viewId,
            id: itemDetails.views[viewId].objects.id[i],
            mask: masksSVG,
            rle: mask_rle,
            catId: itemDetails.views[viewId].objects.category[i].id,
            visible: true,
            opacity: 1.0,
          });
          let item: AnnLabel = {
            id: itemDetails.views[viewId].objects.id[i],
            type: "mask",
            label:
              itemDetails.views[viewId].objects.category[i].name +
              "-" +
              struct_categories[cat_name].items.length,
            visible: true,
            opacity: 1.0,
          };
          struct_categories[cat_name].items.push(item);
        }
      }
      struct_views_categories[viewId] = struct_categories;
    }
    for (let view in struct_views_categories) {
      for (let cat_name in struct_views_categories[view]) {
        annotations.push(struct_views_categories[view][cat_name]);
      }
    }

    console.log("init masksGT", masksGT);
    //unique classes from existing annotations
    for (let ann of annotations) {
      if (!classes.some((cls) => cls.id === ann.category_id)) {
        classes.push({
          id: ann.category_id,
          name: ann.category_name,
        });
      }
    }

    // Embeddings
    console.log("=== LOADING EMBEDDING ===");
    for (let viewId of Object.keys(itemDetails.views)) {
      const embeddingArrByte = await api.getViewEmbedding(
        selectedDataset.id,
        itemDetails.id,
        viewId
      );
      let selectedItemEmbedding = null;
      try {
        const embeddingArr = npyjs.parse(embeddingArrByte);
        selectedItemEmbedding = new ort.Tensor(
          "float32",
          embeddingArr.data,
          embeddingArr.shape
        );
      } catch (err) {
        console.log("Embedding not loaded", err);
      }
      selectedItemEmbeddings[viewId] = selectedItemEmbedding;
    }
    console.log("Embedding:", selectedItemEmbeddings);
    console.log("DONE");
  }

  function toggleUnselectItemConfirm() {
    unselectItemConfirm = !unselectItemConfirm;
  }

  function confirmUnselectItem() {
    saveFlag = false;
    toggleUnselectItemConfirm();
  }

  async function handleUnselectItem() {
    if (!saveFlag) {
      unselectItem();
    } else {
      toggleUnselectItemConfirm();
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
    selectedItemEmbeddings = {};
    masksGT = [];
    annotations = [];
    classes = [];
    curPage = 1;
  }

  function saveAnns(annotations, masksGT) {
    console.log("App - save annotations");
    //format annotation data for export
    let anns = [];
    for (let mask of masksGT) {
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
    curPage = curPage + 1;
    let new_dbImages = await api.getDatasetItems(selectedDataset.id, curPage);
    if (new_dbImages) {
      dbImages.items = dbImages.items.concat(new_dbImages.items);
    } else {
      //end of dataset : reset last page
      curPage = curPage - 1;
    }
  }

  async function toggleModelPrompt() {
    modelPrompt = false;
    // Try loading model name from user input
    try {
      await sam.init("/models/" + modelInput);
      interactiveSegmenterModel.set(sam);
    } catch (e) {
      toggleModelNotFoundWarning();
    }
  }

  function toggleModelNotFoundWarning() {
    modelNotFoundWarning = !modelNotFoundWarning;
  }

  function handleSaveClick() {
    saveAnns(annotations, masksGT);
    saveFlag = false;
  }

  function enableSaveFlag() {
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
  on:saveclick={handleSaveClick}
  on:closeclick={handleUnselectItem}
/>
<div
  class="pt-20 h-screen w-screen text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300"
>
  {#if datasets}
    {#if selectedItem}
      <AnnotationWorkspace
        itemData={selectedItem}
        embeddings={selectedItemEmbeddings}
        bind:annotations
        bind:masksGT
        {classes}
        {dbImages}
        {curPage}
        bind:saveFlag
        on:selectItem={(event) => selectItem(event.detail)}
        on:loadNextPage={handleLoadNextPage}
        on:enableSaveFlag={enableSaveFlag}
      />
    {:else}
      <Library
        {datasets}
        btn_label="Annotate"
        on:datasetclick={selectDataset}
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
      on:confirmed={toggleModelPrompt}
    />
  {/if}
  {#if modelNotFoundWarning}
    <WarningModal
      message="models/{modelInput} was not found in your dataset library."
      details="Please refer to our interactive annotation notebook for information on how to export your model to ONNX."
      moreDetails="Please also check your internet connection, as it is currently required to initialize an ONNX model."
      on:confirmed={toggleModelNotFoundWarning}
    />
  {/if}
  {#if unselectItemConfirm}
    <ConfirmModal
      message="You have unsaved changes."
      confirm="Close without saving"
      on:confirmed={confirmUnselectItem}
      on:canceled={toggleUnselectItemConfirm}
    />
  {/if}
</div>
