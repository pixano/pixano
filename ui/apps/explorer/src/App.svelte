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

  import Header from "../../../components/core/src/Header.svelte";
  import LoadingLibrary from "../../../components/core/src/LoadingLibrary.svelte";
  import Library from "../../../components/core/src/Library.svelte";
  import {
    convertSegmentsToSVG,
    generatePolygonSegments,
  } from "../../../components/models/src/mask_utils";
  import * as api from "./lib/api";
  import DatasetExplorer from "./lib/DatasetExplorer.svelte";
  import ExplorationWorkspace from "./lib/ExplorationWorkspace.svelte";

  import type {
    ItemData,
    MaskGT,
    BBox,
    AnnotationsLabels,
    AnnLabel,
    ViewData,
  } from "../../../components/canvas2d/src/interfaces";

  // Dataset navigation
  let datasets = null;
  let selectedDataset = null;
  let selectedItem: ItemData = null;
  let showDetailsPage: boolean = false;
  let masksGT: Array<MaskGT> = [];
  let bboxes: Array<BBox> = [];
  let annotations: Array<AnnotationsLabels> = [];
  let itemDetails = null;

  async function selectDataset(event: CustomEvent) {
    selectedDataset = event.detail.dataset;
  }

  async function selectItem(event: CustomEvent) {
    showDetailsPage = true;
    //selectedItem = event.detail.id;

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

    //build annotations, masksGT, bboxes and classes
    let struct_categories = {};
    for (let viewId of Object.keys(itemDetails.views)) {
      for (let i = 0; i < itemDetails.views[viewId].objects.id.length; ++i) {
        const mask_rle = itemDetails.views[viewId].objects.segmentation[i];
        const bbox = itemDetails.views[viewId].objects.boundingBox[i];
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

        if (!(bbox || mask_rle)) {
          console.log("WARNING!, no mask nor bounding box!!");
          continue;
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
          if (bbox && bbox.is_predict) {
            item.confidence = bbox.confidence;
          }
          struct_categories[cat_name].items.push(item);
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
          let item: AnnLabel = {
            id: itemDetails.views[viewId].objects.id[i],
            type: "bbox",
            label:
              itemDetails.views[viewId].objects.category[i].name +
              "-" +
              struct_categories[cat_name].items.length,
            visible: true,
            opacity: 1.0,
          };
          if (bbox.is_predict) {
            item.confidence = bbox.confidence;
          }
          struct_categories[cat_name].items.push(item);
        }
      }
    }
    for (let cat_name in struct_categories)
      annotations.push(struct_categories[cat_name]);

    console.log("selectItem Done", masksGT, bboxes, annotations);
  }

  function unselectItem() {
    showDetailsPage = false;
    selectedItem = null;
    masksGT = [];
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
  save_flag={false}
  on:closeclick={unselectItem}
/>
<div
  class="pt-20 h-screen w-screen text-zinc-800 dark:text-zinc-300 dark:bg-zinc-800"
>
  {#if datasets}
    {#if selectedDataset}
      {#if selectedItem}
        <ExplorationWorkspace
          itemData={selectedItem}
          features={itemDetails}
          {annotations}
          {masksGT}
          {bboxes}
          on:closeclick={unselectItem}
        />
      {:else}
        <DatasetExplorer dataset={selectedDataset} on:itemclick={selectItem} />
      {/if}
    {:else}
      <Library {datasets} btn_label="Explore" on:datasetclick={selectDataset} />
    {/if}
  {:else}
    <LoadingLibrary />
  {/if}
</div>
