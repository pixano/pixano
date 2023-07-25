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

  import type { Dataset, ItemData, ItemLabels, Mask, BBox } from "@pixano/core";

  // Dataset navigation
  let datasets: Array<Dataset>;
  let selectedDataset: Dataset;
  let currentPage = 1;

  let selectedItem: ItemData;

  let annotations: ItemLabels = {};
  let classes = [];
  let masks: Array<Mask> = [];
  let bboxes: Array<BBox> = [];

  async function handleSelectDataset(dataset: Dataset) {
    console.log("App.handleSelectDataset");
    selectedDataset = dataset;
  }

  function handleUnselectDataset() {
    handleUnselectItem();
    console.log("App.handleUnselectDataset");
    selectedDataset = null;
    currentPage = 1;
  }

  async function handleSelectItem(id: string) {
    annotations = {};
    classes = [];
    masks = [];

    console.log("App.handleSelectItem");
    const start = Date.now();
    selectedItem = await api.getItemDetails(selectedDataset.id, id);
    console.log(
      "App.handleSelectItem - api.getItemDetails in",
      Date.now() - start,
      "ms"
    );

    for (let view of selectedItem.views) {
      // Initialize annotations
      annotations[view.id] = {
        sources: {},
        numLabels: 0,
        opened: true,
        visible: true,
      };
      for (let sourceId of selectedItem.objects[view.id].maskSources) {
        annotations[view.id].sources[sourceId] = {
          categories: {},
          numLabels: 0,
          opened: true,
          visible: true,
        };
      }

      // Initalize classes
      classes = selectedDataset.categories;

      for (let i = 0; i < selectedItem.objects[view.id].ids.length; ++i) {
        const labelId = selectedItem.objects[view.id].ids[i];
        const maskRLE = selectedItem.objects[view.id].masks[i];
        const bboxXYWH = selectedItem.objects[view.id].bboxes[i];
        const maskSourceId = selectedItem.objects[view.id].maskSources[i];
        const bboxSourceId = selectedItem.objects[view.id].bboxSources[i];
        const catId = selectedItem.objects[view.id].categories[i].id;
        const catName = selectedItem.objects[view.id].categories[i].name;

        // Masks and bounding boxes
        if (maskRLE || bboxXYWH) {
          // Add class if new
          if (!classes.some((cls) => cls.id === catId)) {
            classes.push({
              id: catId,
              name: catName,
            });
          }

          if (maskRLE) {
            const rle = maskRLE["counts"];
            const size = maskRLE["size"];
            const maskPoly = mask_utils.generatePolygonSegments(rle, size[0]);
            const masksSVG = mask_utils.convertSegmentsToSVG(maskPoly);

            // Add category if new
            if (
              !annotations[view.id].sources[maskSourceId].categories[catName]
            ) {
              annotations[view.id].sources[maskSourceId].categories[catName] = {
                labels: {},
                id: catId,
                name: catName,
                opened: false,
                visible: true,
              };
            }

            // Add mask label
            annotations[view.id].sources[maskSourceId].categories[
              catName
            ].labels[`${labelId}_mask`] = {
              id: labelId,
              categoryId: catId,
              categoryName: catName,
              sourceId: maskSourceId,
              viewId: view.id,
              type: "mask",
              confidence:
                bboxXYWH && bboxXYWH.predicted ? bboxXYWH.confidence : null,
              opacity: 1.0,
              visible: true,
            };

            // Add mask
            masks.push({
              id: selectedItem.objects[view.id].ids[i],
              viewId: view.id,
              svg: masksSVG,
              rle: maskRLE,
              catId: selectedItem.objects[view.id].categories[i].id,
              visible: true,
              opacity: 1.0,
            });
          }
          if (bboxXYWH) {
            // Add category if new
            if (
              !annotations[view.id].sources[bboxSourceId].categories[catName]
            ) {
              annotations[view.id].sources[bboxSourceId].categories[catName] = {
                labels: {},
                id: catId,
                name: catName,
                opened: false,
                visible: true,
              };
            }
            // Add bbox label
            annotations[view.id].sources[bboxSourceId].categories[
              catName
            ].labels[`${labelId}_bbox`] = {
              id: labelId,
              categoryId: catId,
              categoryName: catName,
              sourceId: bboxSourceId,
              viewId: view.id,
              type: "bbox",
              confidence: bboxXYWH.predicted ? bboxXYWH.confidence : null,
              opacity: 1.0,
              visible: true,
            };

            // Add bbox
            bboxes.push({
              id: selectedItem.objects[view.id].ids[i],
              viewId: view.id,
              bbox: [bboxXYWH.x, bboxXYWH.y, bboxXYWH.width, bboxXYWH.height], //still normalized
              tooltip:
                selectedItem.objects[view.id].categories[i].name +
                (bboxXYWH.predicted
                  ? " " + bboxXYWH.confidence.toFixed(2)
                  : ""),
              catId: selectedItem.objects[view.id].categories[i].id,
              visible: true,
            });
          }
          annotations[view.id].numLabels += 1;
          annotations[view.id].sources[
            maskSourceId || bboxSourceId
          ].numLabels += 1;
        } else {
          console.log(
            "App.handleSelectItem - Warning: no mask nor bounding box"
          );
          continue;
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
    const start = Date.now();
    datasets = await api.getDatasetsList();
    console.log(
      "App.onMount - api.getDatasetsList in",
      Date.now() - start,
      "ms"
    );
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
          on:selectItem={(event) => handleSelectItem(event.detail.id)}
        />
      {/if}
    {:else}
      <Library
        {datasets}
        buttonLabel="Explore"
        on:selectDataset={(event) => handleSelectDataset(event.detail.dataset)}
      />
    {/if}
  {:else}
    <LoadingLibrary />
  {/if}
</div>
