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

  import { api, ConfirmModal, Header, Library, LoadingLibrary, WarningModal } from "@pixano/core";
  import { mask_utils } from "@pixano/models";

  import AnnotationWorkspace from "./AnnotationWorkspace.svelte";

  import type {
    BBox,
    DatasetCategory,
    DatasetInfo,
    DatasetItem,
    ItemLabels,
    Mask,
  } from "@pixano/core";

  // Dataset navigation
  let models: Array<string>;
  let datasets: Array<DatasetInfo>;
  let selectedDataset: DatasetInfo;
  let currentPage = 1;

  let selectedItem: DatasetItem;
  let annotations: ItemLabels;
  let classes: Array<DatasetCategory>;
  let masks: Array<Mask>;
  let bboxes: Array<BBox>;

  let activeLearningFlag = false;
  let saveFlag = false;

  // Modals
  let unselectItemModal = false;
  let datasetErrorModal = false;

  function until(condition: () => boolean): Promise<void> {
    return new Promise<void>((resolve) => {
      let i = setInterval(() => {
        console.log("App.until - Waiting for user confirmation");
        if (condition()) {
          resolve();
          clearInterval(i);
        }
      }, 500);
    });
  }

  async function handleGetModels() {
    console.log("App.handleGetModels");
    const start = Date.now();
    models = await api.getModels();
    console.log("App.handleGetModels - api.getModels in", Date.now() - start, "ms");
  }

  async function handleGetDatasets() {
    console.log("App.handleGetDatasets");
    const start = Date.now();
    datasets = await api.getDatasets();
    console.log("App.handleGetDatasets - api.getDatasets in", Date.now() - start, "ms");
  }

  async function handleSelectDataset(dataset: DatasetInfo) {
    console.log("App.handleSelectDataset");
    selectedDataset = dataset;
    const start = Date.now();
    selectedDataset.page = await api.getDatasetItems(selectedDataset.id, currentPage);
    console.log("App.handleSelectDataset - api.getDatasetItems in", Date.now() - start, "ms");

    if (selectedDataset.page) {
      // If selected dataset successfully, select first item
      const firstItem = selectedDataset.page.items[0];

      // Toggle active learning filtering if "round" found
      if ("round" in firstItem) {
        activeLearningFlag = true;
      } else {
        activeLearningFlag = false;
      }

      await handleSelectItem(firstItem.id);
    } else {
      // Otherwise display error message
      await handleUnselectDataset();
      datasetErrorModal = true;
    }
  }

  async function handleUnselectDataset() {
    console.log("App.handleUnselectDataset");
    await handleUnselectItem();
    if (!saveFlag) {
      selectedDataset = null;
      currentPage = 1;
      await handleGetDatasets();
    }
  }

  async function handleSelectItem(itemId: string) {
    annotations = {};
    classes = selectedDataset.categories ? selectedDataset.categories : [];
    masks = [];
    bboxes = [];

    const start = Date.now();
    const loadedItem = await api.getDatasetItem(selectedDataset.id, itemId);

    console.log("App.handleSelectItem - api.getDatasetItem in", Date.now() - start, "ms");

    if (loadedItem.objects) {
      for (const obj of Object.values(loadedItem.objects)) {
        const sourceId = obj.source_id;
        const viewId = obj.view_id;
        const catId =
          "category_id" in obj.features ? (obj.features.category_id.value as number) : null;
        const catName =
          "category_name" in obj.features ? (obj.features.category_name.value as string) : null;

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
            const rle = obj.mask.counts;
            const size = obj.mask.size;
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
          const imageWidth = loadedItem.views[viewId].features.width.value as number;
          const imageHeight = loadedItem.views[viewId].features.height.value as number;

          if (obj.bbox && !obj.bbox.coords.every((item) => item == 0)) {
            const x = obj.bbox.coords[0] * imageWidth;
            const y = obj.bbox.coords[1] * imageHeight;
            const w = obj.bbox.coords[2] * imageWidth;
            const h = obj.bbox.coords[3] * imageHeight;
            const confidence =
              obj.bbox.confidence != 0.0 ? " " + obj.bbox.confidence.toFixed(2) : "";

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
    selectedItem = loadedItem;
  }

  async function handleUnselectItem() {
    console.log("App.handleUnselectItem");
    if (!saveFlag) {
      unselectItem();
    } else {
      unselectItemModal = true;
      await until(() => unselectItemModal == false);
      if (!saveFlag) {
        unselectItem();
      }
    }
  }

  function unselectItem() {
    unselectItemModal = false;
    selectedItem = null;
    annotations = {};
    classes = [];
    masks = [];
    bboxes = [];
  }

  async function handleSaveItem() {
    console.log("App.handleSaveItem");

    let savedItem: DatasetItem = {
      id: selectedItem.id,
      split: selectedItem.split,
      views: {},
      features: selectedItem.features,
      objects: {},
      embeddings: {},
    };

    // Return annotations
    for (const sourceLabels of Object.values(annotations)) {
      for (const viewLabels of Object.values(sourceLabels.views)) {
        for (const catLabels of Object.values(viewLabels.categories)) {
          for (const label of Object.values(catLabels.labels)) {
            const mask = masks.find((m) => m.id === label.id && m.viewId === label.viewId);
            const bbox = bboxes.find((b) => b.id === label.id && b.viewId === label.viewId);

            const imageWidth = selectedItem.views[label.viewId].features.width.value as number;
            const imageHeight = selectedItem.views[label.viewId].features.height.value as number;

            savedItem.objects[label.id] = {
              id: label.id,
              item_id: selectedItem.id,
              source_id: label.sourceId,
              view_id: label.viewId,
              bbox: {
                coords: bbox
                  ? [
                      bbox.bbox[0] / imageWidth,
                      bbox.bbox[1] / imageHeight,
                      bbox.bbox[2] / imageWidth,
                      bbox.bbox[3] / imageHeight,
                    ] // normalized
                  : [0, 0, 0, 0],
                format: "xywh",
                is_normalized: true,
                confidence: label.confidence,
              },
              mask: mask
                ? {
                    size: mask.rle ? mask.rle.size : [0, 0],
                    counts: mask.rle ? mask.rle.counts : [],
                  }
                : { size: [0, 0], counts: [] },
              features: {
                category_id: { name: "category_id", dtype: "number", value: label.categoryId },
                category_name: {
                  name: "category_name",
                  dtype: "number",
                  value: label.categoryName,
                },
              },
            };
          }
        }
      }
    }

    const start = Date.now();
    await api.postDatasetItem(selectedDataset.id, savedItem);
    console.log("App.handleSaveItem - api.postDatasetItem in", Date.now() - start, "ms");
    saveFlag = false;

    // Reload item details
    await handleSelectItem(selectedItem.id);
  }

  async function handleLoadNextPage() {
    console.log("App.handleLoadNextPage");
    currentPage = currentPage + 1;

    const start = Date.now();
    const new_dbImages = await api.getDatasetItems(selectedDataset.id, currentPage);
    console.log("App.handleLoadNextPage - api.getDatasetItems in", Date.now() - start, "ms");

    if (new_dbImages) {
      selectedDataset.page.items = selectedDataset.page.items.concat(new_dbImages.items);
    } else {
      // End of dataset: reset last page
      currentPage = currentPage - 1;
    }
  }

  onMount(async () => {
    console.log("App.onMount");
    await handleGetDatasets();
    await handleGetModels();
  });
</script>

{#if datasets}
  {#if selectedDataset}
    <Header
      app="Annotator"
      bind:selectedDataset
      bind:selectedItem
      {saveFlag}
      on:unselectDataset={handleUnselectDataset}
      on:unselectItem={handleUnselectItem}
      on:saveItem={handleSaveItem}
    />
    {#if selectedItem}
      <AnnotationWorkspace
        {selectedDataset}
        {selectedItem}
        bind:annotations
        {classes}
        bind:masks
        bind:bboxes
        {currentPage}
        {models}
        bind:activeLearningFlag
        bind:saveFlag
        on:selectItem={(event) => handleSelectItem(event.detail)}
        on:loadNextPage={handleLoadNextPage}
        on:enableSaveFlag={() => (saveFlag = true)}
      />
    {/if}
  {:else}
    <Library
      {datasets}
      app="Annotator"
      on:selectDataset={(event) => handleSelectDataset(event.detail)}
      on:unselectDataset={handleUnselectDataset}
    />
  {/if}
{:else}
  <LoadingLibrary app="Annotator" />
{/if}
{#if unselectItemModal}
  <ConfirmModal
    message="You have unsaved changes."
    confirm="Close without saving"
    on:confirm={() => ((saveFlag = false), (unselectItemModal = false))}
    on:cancel={() => (unselectItemModal = false)}
  />
{/if}
{#if datasetErrorModal}
  <WarningModal
    message="Error while retrieving dataset items."
    details="Please look at the application logs for more information, and report this issue if the error persists."
    on:confirm={() => (datasetErrorModal = false)}
  />
{/if}
