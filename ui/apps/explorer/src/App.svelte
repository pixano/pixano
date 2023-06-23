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
  import { currentPage } from "./stores";
  import pixanoLogo from "./assets/pixano.png";
  import Library from "./lib/Library.svelte";
  import EmptyLibrary from "./lib/EmptyLibrary.svelte";
  import DatasetExplorer from "./lib/DatasetExplorer.svelte";
  import DatasetItemDetails from "./lib/DatasetItemDetails.svelte";
  import * as api from "./lib/api";
  import type { ItemData, MaskGT, BBox, AnnotationsLabels, AnnLabel, ViewData } from "../../../components/Canvas2D/src/interfaces";
  import { generatePolygonSegments, convertSegmentsToSVG } from "../../../components/models/src/tracer";

  // Dataset navigation
  let datasets = null;
  let selectedDataset = null;
  let selectedItem : ItemData = null;
  let showDetailsPage: boolean = false;
  let masksGT : Array<MaskGT> = [];
  let bboxes : Array<BBox> = [];
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
    let views : Array<ViewData> = [];
    for (let viewId of Object.keys(itemDetails.views)) {
      let view : ViewData = {
        viewId: viewId,
        imageURL: itemDetails.views[viewId].image
      };
      views.push(view);
    }
    selectedItem = {
      dbName: selectedDataset.name,
      imageId: event.detail.id,
      views: views,
    };
    console.log("item loaded:", selectedItem);

    //build annotations, masksGT, bboxes and classes
    let struct_categories = {}
    for (let viewId of Object.keys(itemDetails.views)) {

      for (let i = 0; i < itemDetails.views[viewId].objects.id.length; ++i) {
        const mask_rle = itemDetails.views[viewId].objects.segmentation[i];
        const bbox = itemDetails.views[viewId].objects.boundingBox[i];
        const cat_name = itemDetails.views[viewId].objects.category[i].name;

        // ensure all items goes in unique category (by name)
        if(!struct_categories[cat_name]) {
          let annotation : AnnotationsLabels = {
            viewId: viewId,
            category_name: cat_name,
            category_id: itemDetails.views[viewId].objects.category[i].id,
            items: [],
            visible: true,
          };
          struct_categories[cat_name] = annotation;
        }

        if(!(bbox || mask_rle)) {
          console.log("WARNING!, no mask nor bounding box!!");
          continue;
        }

        if(mask_rle) {
          const rle = mask_rle["counts"];
          const size = mask_rle["size"];
          const maskPolygons = generatePolygonSegments(rle, size[0]);
          const masksSVG = convertSegmentsToSVG(maskPolygons);

          masksGT.push({
            viewId: viewId,
            id: itemDetails.views[viewId].objects.id[i],
            mask: masksSVG,
            rle: mask_rle,
            visible: true,
            opacity: 1.0,
          });
          let item : AnnLabel = {
            id: itemDetails.views[viewId].objects.id[i],
            type: "mask",
            label: itemDetails.views[viewId].objects.category[i].name+"-"+struct_categories[cat_name].items.length,
            visible: true,
            opacity: 1.0,
          };
          struct_categories[cat_name].items.push(item);
        }
        if(bbox) {
          bboxes.push({
            viewId: viewId,
            id: itemDetails.views[viewId].objects.id[i],
            bbox: [bbox.x, bbox.y, bbox.width, bbox.height],  //still normalized
            label: itemDetails.views[viewId].objects.category[i].name + (bbox.is_predict ? " "+parseFloat(bbox.confidence).toFixed(2): ""),
            visible: true
          });
          let item : AnnLabel = {
            id: itemDetails.views[viewId].objects.id[i],
            type: "bbox",
            label: itemDetails.views[viewId].objects.category[i].name+"-"+struct_categories[cat_name].items.length,
            visible: true,
            opacity: 1.0,
          }
          if(bbox.is_predict) {
            item.confidence = bbox.confidence;
          } 
          struct_categories[cat_name].items.push(item);
        }
      }
    }
    for(let cat_name in struct_categories) annotations.push(struct_categories[cat_name]);

    console.log("selectItem Done", masksGT, bboxes, annotations)
  }

  function goToLibrary() {
    selectedDataset = null;
    selectedItem = null;
    currentPage.update((n) => 1);
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

<!-- Header -->
<header class="w-full fixed">
  <div
    class="h-20 py-4 px-4 flex justify-start items-center bg-white border-b-2 dark:bg-zinc-800 dark:border-zinc-700"
  >
    <!-- Logo & app name -->
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div
      class="flex space-x-4 cursor-pointer hover:text-rose-800 dark:hover:text-rose-300"
      on:click={goToLibrary}
    >
      <img src={pixanoLogo} alt="Logo Pixano" class="w-10" />
      <span class="text-3xl font-bold transition-colors">
        Pixano Explorer
      </span>
    </div>
    {#if selectedDataset}
      <span
        class="ml-8 px-2 py-1 flex items-center justify-center bg-zinc-100 text-zinc-600 border rounded-md border-zinc-300 
        dark:bg-zinc-700 dark:text-zinc-300 dark:border-zinc-600"
      >
        {selectedDataset.name}
      </span>
    {/if}

    <!-- Navigation -->
    <div class="mr-4 flex-grow text-right">
      {#if selectedDataset}
        <button
          class="p-2 transition-colors hover:text-rose-800 dark:hover:text-rose-300"
          on:click={goToLibrary}>Back to Library</button
        >
      {/if}
    </div>
  </div>
</header>

<!-- Page offset for header -->
<div class="pt-20" />

{#if !datasets}
  <EmptyLibrary />
{:else if selectedDataset}
  {#if !showDetailsPage}
    <DatasetExplorer dataset={selectedDataset} on:itemclick={selectItem} />
  {:else if selectedItem}
    <DatasetItemDetails
      itemData={selectedItem}
      features={itemDetails}
      {annotations}
      {masksGT}
      {bboxes}
      on:closeclick={unselectItem}
    />
  {/if}
{:else}
  <Library {datasets} on:datasetclick={selectDataset} />
{/if}
