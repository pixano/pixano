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
    Dataset,
    ItemData,
    Mask,
    BBox,
    AnnotationCategory,
    AnnotationLabel,
  } from "@pixano/core";

  // Dataset navigation
  let datasets: Array<Dataset>;
  let selectedDataset: Dataset;
  let currentPage = 1;

  let selectedItem: ItemData;

  let masks: Array<Mask> = [];
  let bboxes: Array<BBox> = [];
  let annotations: Array<AnnotationCategory> = [];

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
    console.log("App.handleSelectItem");
    const start = Date.now();
    selectedItem = await api.getItemDetails(selectedDataset.id, id);
    console.log(
      "App.handleSelectItem - api.getItemDetails in",
      Date.now() - start,
      "ms"
    );

    //build annotations, masks, bboxes and classes
    let struct_categories: { [key: string]: AnnotationCategory } = {};
    for (let view of selectedItem.views) {
      for (let i = 0; i < selectedItem.objects[view.id].id.length; ++i) {
        const maskRLE = selectedItem.objects[view.id].masks[i];
        const bboxXYWH = selectedItem.objects[view.id].bboxes[i];
        const catName = selectedItem.objects[view.id].categories[i].name;

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

        if (!(maskRLE || bboxXYWH)) {
          console.log(
            "App.handleSelectItem - Warning: no mask nor bounding box"
          );
          continue;
        }

        if (maskRLE) {
          const rle = maskRLE["counts"];
          const size = maskRLE["size"];
          const maskPolygons = mask_utils.generatePolygonSegments(rle, size[0]);
          const masksSVG = mask_utils.convertSegmentsToSVG(maskPolygons);

          masks.push({
            viewId: view.id,
            id: selectedItem.objects[view.id].id[i],
            svg: masksSVG,
            rle: maskRLE,
            catId: selectedItem.objects[view.id].categories[i].id,
            visible: true,
            opacity: 1.0,
          });
          let label: AnnotationLabel = {
            id: selectedItem.objects[view.id].id[i],
            viewId: view.id,
            type: "mask",
            visible: true,
            opacity: 1.0,
          };
          if (bboxXYWH && bboxXYWH.predicted) {
            label.confidence = bboxXYWH.confidence;
          }
          struct_categories[catName].labels.push(label);
        }
        if (bboxXYWH) {
          bboxes.push({
            viewId: view.id,
            id: selectedItem.objects[view.id].id[i],
            bbox: [bboxXYWH.x, bboxXYWH.y, bboxXYWH.width, bboxXYWH.height], //still normalized
            tooltip:
              selectedItem.objects[view.id].categories[i].name +
              (bboxXYWH.predicted ? " " + bboxXYWH.confidence.toFixed(2) : ""),
            catId: selectedItem.objects[view.id].categories[i].id,
            visible: true,
          });
          let label: AnnotationLabel = {
            id: selectedItem.objects[view.id].id[i],
            viewId: view.id,
            type: "bbox",
            visible: true,
            opacity: 1.0,
          };
          if (bboxXYWH.predicted) {
            label.confidence = bboxXYWH.confidence;
          }
          struct_categories[catName].labels.push(label);
        }
      }
    }
    for (let catName in struct_categories)
      annotations.push(struct_categories[catName]);
  }

  function handleUnselectItem() {
    console.log("App.handleUnselectItem");
    selectedItem = null;
    masks = [];
    bboxes = [];
    annotations = [];
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
