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

  import DatasetExplorer from "./DatasetExplorer.svelte";
  import ExplorationWorkspace from "./ExplorationWorkspace.svelte";

  import type {
    BBox,
    DatasetCategory,
    DatasetInfo,
    DatasetItem,
    ItemLabels,
    Mask,
  } from "@pixano/core";

  // Dataset navigation
  let datasets: Array<DatasetInfo>;
  let selectedDataset: DatasetInfo;
  let currentPage = 1;

  let selectedItem: DatasetItem;
  let selectedTab: string = "dashboard";

  let annotations: ItemLabels;
  let classes: Array<DatasetCategory>;
  let masks: Array<Mask>;
  let bboxes: Array<BBox>;

  async function handleGetDatasets() {
    console.log("App.handleGetDatasets");
    const start = Date.now();
    datasets = await api.getDatasets();
    console.log("App.handleGetDatasets - api.getDatasets in", Date.now() - start, "ms");
  }

  async function handleSelectDataset(dataset: DatasetInfo) {
    console.log("App.handleSelectDataset");
    const start = Date.now();
    selectedDataset = await api.getDataset(dataset.id);
    console.log("App.handleSelectDataset - api.getDataset in", Date.now() - start, "ms");
  }

  async function handleUnselectDataset() {
    console.log("App.handleUnselectDataset");
    handleUnselectItem();
    selectedDataset = null;
    currentPage = 1;
    await handleGetDatasets();
  }

  async function handleSelectItem(itemId: string) {
    annotations = {};
    classes = selectedDataset.categories ? selectedDataset.categories : [];
    masks = [];
    bboxes = [];

    const start = Date.now();
    selectedItem = await api.getDatasetItem(selectedDataset.id, itemId);

    console.log("App.handleSelectItem - api.getDatasetItem in", Date.now() - start, "ms");

    for (const obj of Object.values(selectedItem.objects)) {
      const sourceId = obj.source_id;
      const viewId = obj.view_id;
      const catId =
        "category_id" in obj.features ? (obj.features["category_id"].value as number) : null;
      const catName =
        "category_name" in obj.features ? (obj.features["category_name"].value as string) : null;

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
        const imageWidth = selectedItem.views[viewId].features["width"].value as number;
        const imageHeight = selectedItem.views[viewId].features["height"].value as number;

        if (obj.bbox && !obj.bbox.coords.every((item) => item == 0)) {
          const x = obj.bbox.coords[0] * imageWidth;
          const y = obj.bbox.coords[1] * imageHeight;
          const w = obj.bbox.coords[2] * imageWidth;
          const h = obj.bbox.coords[3] * imageHeight;
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
        on:selectItem={(event) => handleSelectItem(event.detail)}
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
