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
  import { onMount } from "svelte";
  import Header from "./lib/Header.svelte";
  import Library from "./lib/Library.svelte";
  import EmptyLibrary from "./lib/EmptyLibrary.svelte";
  import DatasetExplorer from "./lib/DatasetExplorer.svelte";
  import AnnotationWorkspace from "./lib/AnnotationWorkspace.svelte";
  import type {
    ItemData,
    MaskGT,
    AnnotationsLabels,
    AnnLabel,
    ViewData,
  } from "../../../components/Canvas2D/src/interfaces";
  import {
    generatePolygonSegments,
    convertSegmentsToSVG,
  } from "../../../components/models/src/tracer";
  import { SAM } from "../../../components/models/src/Sam";
  import * as ort from "onnxruntime-web";
  import * as npyjs from "../../../components/models/src/npy";

  import { interactiveSegmenterModel } from "./stores";

  import * as api from "./lib/api";
  //import type { InteractiveImageSegmenter } from "../../../components/models/src/interactive_image_segmentation";
  //import { MockInteractiveImageSegmenter } from "../../../tools/storybook/stories/components/canvas2d/mocks";

  // Dataset navigation
  let datasets = null;
  let selectedDataset = null;

  let selectedItem: ItemData;
  let selectedItemEmbedding: any;

  let masksGT: Array<MaskGT> = [];
  let annotations: Array<AnnotationsLabels> = [];
  let classes = [];
  let itemDetails = null;

  let showDetailsPage: boolean = false;

  let sam = new SAM();
  //let mock = new MockInteractiveImageSegmenter();

  async function selectDataset(event: CustomEvent) {
    selectedDataset = event.detail.dataset;
  }

  async function selectItem(event: CustomEvent) {
    showDetailsPage = true;

    //selected item
    console.log("=== LOADING SELECTED ITEM ===");
    const start = Date.now();
    itemDetails = await api.getItemDetails(selectedDataset.id, event.detail.id);
    console.log("so long ?? (ms)", Date.now() - start);
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
      imageId: event.detail.id,
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
            catID: itemDetails.views[viewId].objects.category[i].id,
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

    //unique classes from existing annotations
    const cat_set = new Set();
    for (let ann of annotations) cat_set.add(ann.category_name);
    for (let cat of cat_set) {
      classes.push({
        id: classes.length,
        name: cat,
      });
    }

    // Embeddings
    console.log("=== LOADING EMBEDDING ===");
    const embeddingArrByte = await api.getImageEmbedding(
      selectedDataset.id,
      itemDetails.id,
      itemDetails.viewId
    );
    try {
      const embeddingArr = npyjs.parse(embeddingArrByte);
      selectedItemEmbedding = new ort.Tensor(
        "float32",
        embeddingArr.data,
        embeddingArr.shape
      );
    } catch (err) {
      console.log("Embedding not loaded", err);
      selectedItemEmbedding = null;
    }
    console.log("Embedding:", selectedItemEmbedding);
    console.log("DONE");
  }

  function unselectItem() {
    showDetailsPage = false;
    selectedItem = null;
    selectedItemEmbedding = null;
    masksGT = [];
    annotations = [];
    classes = [];
  }

  function findCategoryForId(
    anns: Array<AnnotationsLabels>,
    id: string
  ): string {
    for (let ann of anns) {
      if (ann.items.some((it) => it.id === id)) {
        return ann.category_name;
      }
    }
    console.log("ERROR - unable to find category for id:", id);
    return "undefined";
  }

  function saveAnns(data) {
    /* TODO: adapter pour multivue
    console.log("App - save annotations");
    console.log("data", data.detail);
    //format annotation data for export
    let anns = [];
    for(let mask of data.detail.masks) {
      const category = findCategoryForId(data.detail.anns, mask.id);
      let ann = {
        id: mask.id,
        view_id: selectedItem.viewId,
        category_name: category,
        mask: mask.rle,
        mask_source: "Pixano Annotator"
      };
      anns.push(ann)
    }
    api.postAnnotations(anns, selectedDataset.id, selectedItem.imageId, selectedItem.viewId);
    */
  }

  onMount(async () => {
    datasets = await api.getDatasetsList();

    //TODO: const model = await getModel();
    await sam.init("/models/sam_vit_h_4b8939.onnx");

    interactiveSegmenterModel.set(sam);
    //console.log("SAM input names:", sam.inputNames());
  });
</script>

{#if !datasets}
  <Header bind:selectedDataset bind:selectedItem />
  <div class="pt-20">
    <EmptyLibrary />
  </div>
{:else if selectedDataset}
  {#if !showDetailsPage}
    <Header bind:selectedDataset bind:selectedItem />
    <div class="pt-20">
      <DatasetExplorer dataset={selectedDataset} on:itemclick={selectItem} />
    </div>
  {:else if selectedItem}
    <AnnotationWorkspace
      itemData={selectedItem}
      embedding={selectedItemEmbedding}
      {annotations}
      {masksGT}
      {classes}
      handleCloseClick={unselectItem}
      dataset={selectedDataset}
      on:imageSelected={selectItem}
      on:saveAnns={saveAnns}
    />
  {/if}
{:else}
  <Header bind:selectedDataset bind:selectedItem />
  <div class="pt-20">
    <Library {datasets} on:datasetclick={selectDataset} />
  </div>
{/if}
