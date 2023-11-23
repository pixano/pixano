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

  import { api, Header, Library, LoadingLibrary, WarningModal } from "@pixano/core";
  import { mask_utils } from "@pixano/models";

  import DatasetExplorer from "./DatasetExplorer.svelte";
  import ExplorationWorkspace from "./ExplorationWorkspace.svelte";

  import type { BBox, CategoryData, Dataset, ItemData, ItemLabels, Mask } from "@pixano/core";

  // Dataset navigation
  let datasets: Array<Dataset>;
  let selectedDataset: Dataset;
  let currentPage = 1;

  let query = "";

  let selectedItem: ItemData;
  let selectedTab: string = "dashboard";

  let annotations: ItemLabels;
  let classes: Array<CategoryData>;
  let masks: Array<Mask>;
  let bboxes: Array<BBox>;

  let datasetErrorModal = false;
  let searchErrorModal = false;

  async function handleGetDatasets() {
    console.log("App.handleGetDatasets");
    const start = Date.now();
    datasets = await api.getDatasetList();
    console.log("App.handleGetDatasets - api.getDatasetList in", Date.now() - start, "ms");
  }

  function handleSelectDataset(dataset: Dataset) {
    console.log("App.handleSelectDataset");
    selectedDataset = dataset;
  }

  async function handleUnselectDataset() {
    console.log("App.handleUnselectDataset");
    handleUnselectItem();
    selectedDataset = null;
    currentPage = 1;
    query = "";
    await handleGetDatasets();
  }

  async function handleSelectItem(itemId: string) {
    annotations = {};
    classes = selectedDataset.categories;
    masks = [];
    bboxes = [];

    const start = Date.now();
    const itemDetails = await api.getItemDetails(selectedDataset.id, itemId);
    selectedItem = itemDetails["itemData"];
    const itemObjects = itemDetails["itemObjects"];

    console.log("App.handleSelectItem - api.getItemDetails in", Date.now() - start, "ms");

    for (const obj of itemObjects) {
      const sourceId = obj.source_id;
      const viewId = obj.view_id;
      const catId = obj.category_id;
      const catName = obj.category_name;

      // Initialize source annotations
      if (!annotations[sourceId]) {
        annotations[sourceId] = {
          id: sourceId,
          views: {},
          numLabels: 0,
          opened: false,
          visible: true,
        };
      }

      // Initialize view annotations
      if (!annotations[sourceId].views[viewId]) {
        annotations[sourceId].views[viewId] = {
          id: viewId,
          categories: {},
          numLabels: 0,
          opened: false,
          visible: true,
        };
      }

      // Initialize category annotations
      if (!annotations[sourceId].views[viewId].categories[catId]) {
        annotations[sourceId].views[viewId].categories[catId] = {
          labels: {},
          id: catId,
          name: catName,
          opened: false,
          visible: true,
        };
      }

      // Masks and bounding boxes
      if (obj.mask || obj.bbox) {
        // Add label
        annotations[sourceId].views[viewId].categories[catId].labels[obj.id] = {
          id: obj.id,
          categoryId: catId,
          categoryName: catName,
          sourceId: sourceId,
          viewId: viewId,
          confidence: obj.bbox && obj.bbox.confidence != 0.0 ? obj.bbox.confidence : null,
          bboxOpacity: 1.0,
          maskOpacity: 1.0,
          visible: true,
        };

        // Update counters
        annotations[sourceId].numLabels += 1;
        annotations[sourceId].views[viewId].numLabels += 1;

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

        // Add mask
        if (obj.mask) {
          const rle = obj.mask["counts"];
          const size = obj.mask["size"];
          const maskPoly = mask_utils.generatePolygonSegments(rle, size[0]);
          const masksSVG = mask_utils.convertSegmentsToSVG(maskPoly);

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

        // Add bbox
        if (obj.bbox) {
          const x = obj.bbox.coords[0] * selectedItem.views[viewId].width;
          const y = obj.bbox.coords[1] * selectedItem.views[viewId].height;
          const w = obj.bbox.coords[2] * selectedItem.views[viewId].width;
          const h = obj.bbox.coords[3] * selectedItem.views[viewId].height;
          const confidence = obj.bbox.confidence != 0.0 ? " " + obj.bbox.confidence.toFixed(2) : "";

          bboxes.push({
            id: obj.id,
            viewId: viewId,
            bbox: [x, y, w, h], // denormalized
            tooltip: catName + confidence,
            catId: catId,
            visible: true,
            opacity: 1.0,
          });
        }
      } else {
        console.log("App.handleSelectItem - Warning: no mask nor bounding box for item", obj.id);
        continue;
      }
    }

    // Open source annotations if only one source
    const sources = Object.keys(annotations);
    if (sources.length == 1) {
      annotations[sources[0]].opened = true;
    }

    // Open view annotations if only one view
    for (const sourceId of sources) {
      const views = Object.keys(annotations[sourceId].views);
      if (views.length == 1) {
        console.log("open", views[0]);
        annotations[sourceId].views[views[0]].opened = true;
      }
    }
  }

  function handleUnselectItem() {
    console.log("App.handleUnselectItem");
    selectedItem = null;
    annotations = {};
    classes = [];
    masks = [];
    bboxes = [];
  }

  onMount(async () => {
    console.log("App.onMount");
    await handleGetDatasets();
  });
</script>

<Header
  app="Explorer"
  bind:selectedDataset
  bind:selectedItem
  bind:selectedTab
  saveFlag={false}
  on:unselectDataset={handleUnselectDataset}
  on:unselectItem={handleUnselectItem}
/>
{#if datasets}
  {#if selectedDataset}
    {#if selectedItem}
      <ExplorationWorkspace
        {selectedItem}
        {annotations}
        {classes}
        {masks}
        {bboxes}
        on:unselectItem={handleUnselectItem}
      />
    {:else}
      <DatasetExplorer
        bind:selectedTab
        {selectedDataset}
        {currentPage}
        bind:query
        on:selectItem={(event) => handleSelectItem(event.detail)}
        on:datasetError={() => (handleUnselectDataset(), (datasetErrorModal = true))}
        on:searchError={() => (searchErrorModal = true)}
      />
    {/if}
  {:else}
    <Library
      {datasets}
      app="Explorer"
      on:selectDataset={(event) => handleSelectDataset(event.detail)}
    />
  {/if}
{:else}
  <LoadingLibrary app="Explorer" />
{/if}
{#if datasetErrorModal}
  <WarningModal
    message="Error while retrieving dataset items."
    details="Please look at the application logs for more information, and report this issue if the error persists."
    on:confirm={() => (datasetErrorModal = false)}
  />
{/if}
{#if searchErrorModal}
  <WarningModal
    message="Error in Semantic Search"
    details="No Semantics Embeddings, Semantic search not available"
    on:confirm={() => (searchErrorModal = false)}
  />
{/if}
