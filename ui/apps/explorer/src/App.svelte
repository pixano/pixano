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
  import { onMount } from "svelte";

  import { api, Header, Library, LoadingLibrary } from "@pixano/core";
  import { mask_utils } from "@pixano/models";

  import DatasetExplorer from "./lib/DatasetExplorer.svelte";
  import ExplorationWorkspace from "./lib/ExplorationWorkspace.svelte";

  import type {
    ItemData,
    Mask,
    BBox,
    AnnotationCategory,
    AnnotationLabel,
    ViewData,
  } from "@pixano/core/src/interfaces";

  // Dataset navigation
  let datasets = null;
  let selectedDataset = null;
  let currentPage = 1;

  let selectedItem: ItemData = null;

  let masks: Array<Mask> = [];
  let bboxes: Array<BBox> = [];
  let annotations: Array<AnnotationCategory> = [];
  let itemDetails = null;

  async function handleSelectDataset(event: CustomEvent) {
    selectedDataset = event.detail.dataset;
  }

  async function handleSelectItem(event: CustomEvent) {
    //selected item
    console.log("=== LOADING SELECTED ITEM ===");
    itemDetails = await api.getItemDetails(selectedDataset.id, event.detail.id);
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
      id: event.detail.id,
      views: views,
    };
    console.log("item loaded:", selectedItem);

    //build annotations, masks, bboxes and classes
    let struct_categories: { [key: string]: AnnotationCategory } = {};
    for (let viewId of Object.keys(itemDetails.views)) {
      for (let i = 0; i < itemDetails.views[viewId].objects.id.length; ++i) {
        const mask_rle = itemDetails.views[viewId].objects.segmentation[i];
        const bbox = itemDetails.views[viewId].objects.boundingBox[i];
        const cat_name = itemDetails.views[viewId].objects.category[i].name;

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

        if (!(bbox || mask_rle)) {
          console.log("WARNING!, no mask nor bounding box!!");
          continue;
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
            visible: true,
            opacity: 1.0,
          });
          let label: AnnotationLabel = {
            id: itemDetails.views[viewId].objects.id[i],
            viewId: viewId,
            type: "mask",
            visible: true,
            opacity: 1.0,
          };
          if (bbox && bbox.is_predict) {
            label.confidence = bbox.confidence;
          }
          struct_categories[cat_name].labels.push(label);
        }
        if (bbox) {
          bboxes.push({
            viewId: viewId,
            id: itemDetails.views[viewId].objects.id[i],
            bbox: [bbox.x, bbox.y, bbox.width, bbox.height], //still normalized
            label:
              itemDetails.views[viewId].objects.category[i].name +
              (bbox.is_predict
                ? " " + parseFloat(bbox.confidence).toFixed(2)
                : ""),
            catId: itemDetails.views[viewId].objects.category[i].id,
            visible: true,
          });
          let label: AnnotationLabel = {
            id: itemDetails.views[viewId].objects.id[i],
            viewId: viewId,
            type: "bbox",
            visible: true,
            opacity: 1.0,
          };
          if (bbox.is_predict) {
            label.confidence = bbox.confidence;
          }
          struct_categories[cat_name].labels.push(label);
        }
      }
    }
    for (let cat_name in struct_categories)
      annotations.push(struct_categories[cat_name]);

    console.log("selectItem Done", masks, bboxes, annotations);
  }

  function handleUnselectDataset() {
    selectedDataset = null;
    selectedItem = null;
    currentPage = 1;
  }

  function handleUnselectItem() {
    selectedItem = null;
    masks = [];
    bboxes = [];
    annotations = [];
  }

  onMount(async () => {
    datasets = await api.getDatasetsList();
  });
</script>

<Header
  app="Explorer"
  bind:selectedDataset
  bind:selectedItem
  saveFlag={false}
  on:unselectDataset={handleUnselectDataset}
  on:unselectItem={handleUnselectItem}
/>
<div
  class="pt-20 h-screen w-screen text-zinc-800 dark:text-zinc-300 dark:bg-zinc-800"
>
  {#if datasets}
    {#if selectedDataset}
      {#if selectedItem}
        <ExplorationWorkspace
          {selectedItem}
          features={itemDetails}
          {annotations}
          {masks}
          {bboxes}
          on:unselectItem={handleUnselectItem}
        />
      {:else}
        <DatasetExplorer
          {selectedDataset}
          {currentPage}
          on:selectItem={handleSelectItem}
        />
      {/if}
    {:else}
      <Library
        {datasets}
        buttonLabel="Explore"
        on:selectDataset={handleSelectDataset}
      />
    {/if}
  {:else}
    <LoadingLibrary />
  {/if}
</div>
