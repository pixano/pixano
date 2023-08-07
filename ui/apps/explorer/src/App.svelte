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
    Dataset,
    ItemData,
    ItemLabels,
    ItemObjects,
    Mask,
    BBox,
  } from "@pixano/core";

  // Dataset navigation
  let datasets: Array<Dataset>;
  let selectedDataset: Dataset;
  let currentPage = 1;

  let selectedItem: ItemData;

  let annotations: ItemLabels = {};
  let classes = [];
  let masks: Array<Mask> = [];
  let bboxes: Array<BBox> = [];

  async function handleGetDatasets() {
    console.log("App.handleGetDatasets");
    const start = Date.now();
    datasets = await api.getDatasetsList();
    console.log(
      "App.handleGetDatasets - api.getDatasetsList in",
      Date.now() - start,
      "ms"
    );
  }

  async function handleSelectDataset(dataset: Dataset) {
    console.log("App.handleSelectDataset");
    selectedDataset = dataset;
  }

  function handleUnselectDataset() {
    console.log("App.handleUnselectDataset");
    handleUnselectItem();
    selectedDataset = null;
    currentPage = 1;
    handleGetDatasets();
  }

  async function handleSelectItem(itemId: string) {
    annotations = {};
    classes = [];
    masks = [];
    bboxes = [];

    const start = Date.now();
    let itemDetails = await api.getItemDetails(selectedDataset.id, itemId);
    selectedItem = itemDetails["itemData"] as ItemData;
    let ItemObjects = itemDetails["itemObjects"] as ItemObjects;

    console.log(
      "App.handleSelectItem - api.getItemDetails in",
      Date.now() - start,
      "ms"
    );

    for (const [sourceId, sourceObjects] of Object.entries(ItemObjects)) {
      // Initialize annotations
      annotations[sourceId] = {
        id: sourceId,
        views: {},
        numLabels: 0,
        opened: Object.entries(ItemObjects).length > 1 ? false : true,
        visible: true,
      };

      for (const [viewId, viewObjects] of Object.entries(sourceObjects)) {
        // Initialize annotations
        annotations[sourceId].views[viewId] = {
          id: viewId,
          categories: {},
          numLabels: 0,
          opened: Object.entries(sourceObjects).length > 1 ? false : true,
          visible: true,
        };

        for (let obj of viewObjects) {
          const catId = obj.category.id;
          const catName = obj.category.name;

          // Masks and bounding boxes
          if (obj.mask || obj.bbox) {
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

            // Add label
            annotations[sourceId].views[viewId].categories[catId].labels[
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
            annotations[sourceId].numLabels += 1;
            annotations[sourceId].views[viewId].numLabels += 1;

            if (obj.mask) {
              const rle = obj.mask["counts"];
              const size = obj.mask["size"];
              const maskPoly = mask_utils.generatePolygonSegments(rle, size[0]);
              const masksSVG = mask_utils.convertSegmentsToSVG(maskPoly);

              // Add mask
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

            if (obj.bbox) {
              // Add bbox
              bboxes.push({
                id: obj.id,
                viewId: viewId,
                bbox: [
                  obj.bbox.x * selectedItem.views[viewId].width,
                  obj.bbox.y * selectedItem.views[viewId].height,
                  obj.bbox.width * selectedItem.views[viewId].width,
                  obj.bbox.height * selectedItem.views[viewId].height,
                ], // denormalized
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
    handleGetDatasets();
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
  class="pt-20 h-screen w-full
  bg-white dark:bg-zinc-800
  text-zinc-800 dark:text-zinc-300"
>
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
          {selectedDataset}
          {currentPage}
          on:selectItem={(event) => handleSelectItem(event.detail)}
        />
      {/if}
    {:else}
      <Library
        {datasets}
        buttonLabel="Explore"
        on:selectDataset={(event) => handleSelectDataset(event.detail)}
      />
    {/if}
  {:else}
    <LoadingLibrary />
  {/if}
</div>
